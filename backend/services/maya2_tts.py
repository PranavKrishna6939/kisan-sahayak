"""Pipecat TTSService backed by Maya 2 Native (maya3.server WS /v1/tts/stream).

Features:
- Streams 24 kHz mono s16le PCM chunks incrementally as Maya 2 Native generates them.
- Immediate server-side synthesis cancellation (`{"type": "cancel", "context_id": ...}`) on barge-in.
- Automatic Unicode script verification so Maya 2 Native always receives the exact matching language tag.
- Cleans any stray markdown/thinking artifacts before synthesis.
"""

from __future__ import annotations

import asyncio
import base64
import json
import re
import struct
import time
import uuid
from typing import AsyncGenerator, Optional

import aiohttp
from loguru import logger
from pipecat.frames.frames import (
    CancelFrame,
    ErrorFrame,
    Frame,
    InterruptionFrame,
    TTSAudioRawFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.services.settings import TTSSettings
from pipecat.services.tts_service import TTSService

from backend.config import TTS_HTTP_URL, TTS_WS_URL, detect_script_language
from backend.services.session_state import CallSessionState

_MARKDOWN_RE = re.compile(r"[*_`#~>|]+")
_THINK_RE = re.compile(r"<think>.*?</think>", flags=re.DOTALL)
_WS_RE = re.compile(r"\s+")


def _clean_for_speech(text: str) -> str:
    text = _THINK_RE.sub("", text)
    text = _MARKDOWN_RE.sub("", text)
    text = _WS_RE.sub(" ", text).strip()
    return text


def _parse_maya_binary_frame(data: bytes) -> tuple[str, bytes]:
    (n,) = struct.unpack_from("<I", data)
    return data[4 : 4 + n].decode("utf-8"), data[4 + n :]


class Maya2TTSService(TTSService):
    """Streaming TTS service connecting to local Maya 2 Native WebSocket server."""

    def __init__(
        self,
        session: CallSessionState,
        ws_url: str = TTS_WS_URL,
        http_url: str = TTS_HTTP_URL,
        sample_rate: int = 24000,
        **kwargs,
    ):
        super().__init__(
            sample_rate=sample_rate,
            settings=TTSSettings(
                model="maya-research/maya2-native",
                voice=session.voice,
                language=session.detected_language,
            ),
            **kwargs,
        )
        self._session = session
        self._ws_url = ws_url
        self._http_url = http_url.rstrip("/")
        self._http_session: Optional[aiohttp.ClientSession] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._reader_task: Optional[asyncio.Task] = None
        self._queues: dict[str, asyncio.Queue] = {}
        self._active_cids: set[str] = set()
        self._connect_lock = asyncio.Lock()

    async def _ensure_connected(self) -> None:
        if self._ws is not None and not self._ws.closed:
            return
        async with self._connect_lock:
            if self._ws is not None and not self._ws.closed:
                return
            if self._http_session is None or self._http_session.closed:
                self._http_session = aiohttp.ClientSession()
            self._ws = await self._http_session.ws_connect(
                self._ws_url, max_msg_size=16 * 1024 * 1024, heartbeat=25.0
            )
            meta = await self._ws.receive_json()
            logger.debug(f"[{self._session.session_id}] Connected to Maya 2 Native WS: {meta}")
            self._reader_task = asyncio.create_task(self._read_loop())

    async def _read_loop(self) -> None:
        assert self._ws is not None
        try:
            async for msg in self._ws:
                if msg.type == aiohttp.WSMsgType.BINARY:
                    cid, pcm = _parse_maya_binary_frame(msg.data)
                    item = ("audio", pcm)
                elif msg.type == aiohttp.WSMsgType.TEXT:
                    m = json.loads(msg.data)
                    cid = m.get("context_id")
                    if m.get("type") == "audio":
                        item = ("audio", base64.b64decode(m["audio"]))
                    else:
                        item = (m.get("type"), m)
                else:
                    break

                q = self._queues.get(cid)
                if q is not None:
                    q.put_nowait(item)
                elif cid is None and item[0] == "error":
                    for qq in self._queues.values():
                        qq.put_nowait(item)
        except Exception as exc:
            logger.debug(f"[{self._session.session_id}] Maya 2 WS reader ended: {exc}")
        finally:
            for qq in self._queues.values():
                qq.put_nowait(("closed", None))

    async def _cancel_active_contexts(self) -> None:
        if self._ws is None or self._ws.closed:
            self._active_cids.clear()
            return
        for cid in list(self._active_cids):
            try:
                await self._ws.send_json({"type": "cancel", "context_id": cid})
            except Exception:
                pass
            q = self._queues.get(cid)
            if q is not None:
                q.put_nowait(("cancelled", None))
        self._active_cids.clear()

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        if isinstance(frame, (InterruptionFrame, CancelFrame)):
            await self._cancel_active_contexts()
        await super().process_frame(frame, direction)

    async def cleanup(self):
        await self._cancel_active_contexts()
        if self._ws is not None and not self._ws.closed:
            await self._ws.close()
        if self._reader_task is not None:
            self._reader_task.cancel()
            await asyncio.gather(self._reader_task, return_exceptions=True)
        if self._http_session is not None and not self._http_session.closed:
            await self._http_session.close()
        await super().cleanup()

    async def run_tts(self, text: str, context_id: str) -> AsyncGenerator[Frame, None]:
        cleaned = _clean_for_speech(text)
        if not cleaned:
            return

        # Verify script of this sentence matches the TTS language tag
        fallback_lang = self._session.get_tts_language()
        tts_lang = detect_script_language(cleaned, fallback=fallback_lang)
        voice = self._session.voice

        cid = f"{context_id[:8]}-{uuid.uuid4().hex[:6]}"
        t0 = time.perf_counter()
        first_chunk_ms: Optional[int] = None

        try:
            await self._ensure_connected()
            assert self._ws is not None

            q: asyncio.Queue = asyncio.Queue()
            self._queues[cid] = q
            self._active_cids.add(cid)

            yield TTSStartedFrame(context_id=context_id)
            await self._ws.send_json({
                "type": "speak",
                "context_id": cid,
                "text": cleaned,
                "language": tts_lang,
                "voice": voice,
                "binary": True,
                "normalize": True,
            })

            done = False
            try:
                while True:
                    kind, payload = await q.get()
                    if kind == "audio":
                        if first_chunk_ms is None:
                            first_chunk_ms = int((time.perf_counter() - t0) * 1000)
                            logger.info(
                                f"[{self._session.session_id}] Maya2 TTS TTFA={first_chunk_ms}ms "
                                f"(lang={tts_lang}, voice={voice}): {cleaned[:60]}"
                            )
                        if payload:
                            yield TTSAudioRawFrame(
                                audio=payload,
                                sample_rate=24000,
                                num_channels=1,
                                context_id=context_id,
                            )
                    elif kind == "end":
                        done = True
                        break
                    elif kind == "cancelled":
                        done = True
                        break
                    elif kind == "error":
                        done = True
                        logger.error(f"[{self._session.session_id}] Maya2 error: {payload}")
                        yield ErrorFrame(error=f"Maya2 TTS error: {payload}")
                        break
                    elif kind == "closed":
                        done = True
                        break
            finally:
                if not done and self._ws is not None and not self._ws.closed:
                    try:
                        await self._ws.send_json({"type": "cancel", "context_id": cid})
                    except Exception:
                        pass
                self._active_cids.discard(cid)
                self._queues.pop(cid, None)
                yield TTSStoppedFrame(context_id=context_id)

        except Exception as exc:
            logger.error(f"[{self._session.session_id}] Maya2 WS stream failed: {exc}")
            # Reset broken socket for next turn
            self._ws = None
            yield ErrorFrame(error=f"Maya2 TTS connection error: {exc}")
