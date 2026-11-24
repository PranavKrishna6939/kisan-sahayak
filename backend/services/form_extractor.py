"""UI Event Bridge + Asynchronous Parallel Form Extractor (Qwen3.5-9B JSON Delta Patch).

Split cleanly into two Pipecat FrameProcessors:
1. InputEventProcessor (between STT and user_aggregator):
   - Observes VADUserStartedSpeakingFrame / VADUserStoppedSpeakingFrame for instant barge-in UI flush.
2. OutputTranscriptAndExtractorProcessor (between LLM and TTS):
   - Streams LLMFullResponseStartFrame / LLMTextFrame / LLMFullResponseEndFrame to the left transcript pane.
   - Observes InterruptionFrame and upstream BotStartedSpeakingFrame / BotStoppedSpeakingFrame.
   - Fires non-blocking Qwen3.5-9B JSON delta extraction right on LLMFullResponseEndFrame
     (while Maya 2 Native speaks the response!) so the Voice LLM gets 100% uncontended GPU latency
     and the right-hand loan form updates in real time (~400 ms).
"""

from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from typing import Any

import httpx
from loguru import logger
from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    Frame,
    InterruptionFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from backend.config import LLM_MODEL, OLLAMA_BASE_URL, detect_script_language, load_prompt
from backend.services.session_state import CallSessionState

EXTRACTOR_SYSTEM_PROMPT = load_prompt("form_extractor_system.md")
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", flags=re.DOTALL)


def _parse_json_object(raw: str) -> dict[str, Any]:
    raw = (raw or "").strip()
    if not raw:
        return {}
    m = _JSON_FENCE_RE.search(raw)
    if m:
        raw = m.group(1).strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        parsed = json.loads(raw[start : end + 1])
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


class InputEventAndExtractorProcessor(FrameProcessor):
    """Placed after STT, before user_aggregator: handles VAD state & barge-in flush."""

    def __init__(self, session: CallSessionState, **kwargs):
        super().__init__(**kwargs)
        self._session = session

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, VADUserStartedSpeakingFrame):
            if not self._session.bot_speaking:
                await self._session.send_ui_event({"type": "state", "state": "listening"})

        elif isinstance(frame, VADUserStoppedSpeakingFrame):
            await self._session.send_ui_event({"type": "state", "state": "transcribing"})

        await self.push_frame(frame, direction)


class OutputTranscriptProcessor(FrameProcessor):
    """Placed between LLM and TTS: streams agent transcript deltas & runs async form extraction."""

    def __init__(self, session: CallSessionState, **kwargs):
        super().__init__(**kwargs)
        self._session = session
        self._client = httpx.AsyncClient(timeout=20.0)
        self._extract_lock = asyncio.Lock()
        self._bg_tasks: set[asyncio.Task] = set()

    async def cleanup(self):
        for t in list(self._bg_tasks):
            t.cancel()
        await asyncio.gather(*self._bg_tasks, return_exceptions=True)
        await self._client.aclose()
        await super().cleanup()

    def _spawn_extraction(self) -> None:
        task = asyncio.create_task(self._run_extraction())
        self._bg_tasks.add(task)
        task.add_done_callback(self._bg_tasks.discard)

    async def _run_extraction(self) -> None:
        async with self._extract_lock:
            recent = self._session.transcript[-6:]
            if not any(m["role"] == "user" for m in recent):
                return
            convo_lines = [
                f"{'Farmer' if m['role'] == 'user' else 'Kisan Sahayak'}: {m['text']}"
                for m in recent
            ]
            current_filled = {
                k: v for k, v in self._session.application.model_dump().items() if v
            }
            user_payload = (
                f"Already filled:\n{json.dumps(current_filled, ensure_ascii=False)}\n\n"
                f"Recent conversation:\n" + "\n".join(convo_lines) + "\n\n"
                "Output ONLY the JSON object of new or corrected fields (or {}):"
            )

            t0 = time.perf_counter()
            try:
                resp = await self._client.post(
                    f"{OLLAMA_BASE_URL}/api/chat",
                    json={
                        "model": LLM_MODEL,
                        "messages": [
                            {"role": "system", "content": EXTRACTOR_SYSTEM_PROMPT},
                            {"role": "user", "content": user_payload},
                        ],
                        "think": False,
                        "stream": False,
                        "options": {"temperature": 0.0, "num_predict": 320},
                        "keep_alive": "24h",
                    },
                )
                resp.raise_for_status()
                body = resp.json()
                content = (body.get("message") or {}).get("content") or ""
                patch = _parse_json_object(content)
                ms = int((time.perf_counter() - t0) * 1000)
                if patch:
                    changed = self._session.application.apply_patch(patch)
                    if changed:
                        logger.info(
                            f"[{self._session.session_id}] Extracted {len(changed)} fields in {ms}ms: {changed}"
                        )
                        await self._session.emit_form_update(changed_fields=changed)
                else:
                    logger.debug(f"[{self._session.session_id}] Extractor returned empty patch in {ms}ms")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(f"[{self._session.session_id}] Form extraction error: {exc!r}")

    async def _finalize_assistant_message(self, interrupted: bool = False) -> None:
        msg_id = self._session.current_assistant_msg_id
        text = self._session.current_assistant_buffer.strip()
        self._session.current_assistant_msg_id = None
        self._session.current_assistant_buffer = ""
        if msg_id and text:
            # If the user explicitly asked to switch languages (e.g. "speak in English/Tamil")
            # and the LLM complied in the new script, sync the session's sticky language prior!
            if not interrupted and self._session.language_mode in ("auto", "auto_all"):
                reply_lang = detect_script_language(text, fallback=self._session.detected_language)
                if reply_lang != self._session.detected_language:
                    await self._session.set_detected_language(reply_lang, confidence=0.99)
            entry = await self._session.append_transcript(
                role="assistant", text=text, msg_id=msg_id, interrupted=interrupted
            )
            await self._session.send_ui_event({
                "type": "transcript_done",
                "message": entry,
            })
            await self._session.persist()

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, InterruptionFrame):
            await self._session.send_ui_event({"type": "interrupt"})
            self._session.bot_speaking = False
            await self._finalize_assistant_message(interrupted=True)
            await self._session.send_ui_event({"type": "state", "state": "listening"})

        elif isinstance(frame, LLMFullResponseStartFrame):
            self._session.current_assistant_msg_id = uuid.uuid4().hex[:10]
            self._session.current_assistant_buffer = ""
            await self._session.send_ui_event({
                "type": "transcript_start",
                "id": self._session.current_assistant_msg_id,
                "role": "assistant",
                "language": self._session.detected_language,
            })

        elif isinstance(frame, LLMTextFrame):
            if not self._session.current_assistant_msg_id:
                self._session.current_assistant_msg_id = uuid.uuid4().hex[:10]
                self._session.current_assistant_buffer = ""
            self._session.current_assistant_buffer += frame.text
            await self._session.send_ui_event({
                "type": "transcript_delta",
                "id": self._session.current_assistant_msg_id,
                "delta": frame.text,
            })

        elif isinstance(frame, LLMFullResponseEndFrame):
            await self._finalize_assistant_message(interrupted=False)
            # Fire non-blocking form extraction now that Voice LLM finished streaming
            self._spawn_extraction()

        elif isinstance(frame, BotStartedSpeakingFrame):
            self._session.bot_speaking = True
            await self._session.send_ui_event({"type": "state", "state": "speaking"})

        elif isinstance(frame, BotStoppedSpeakingFrame):
            self._session.bot_speaking = False
            await self._session.send_ui_event({"type": "state", "state": "idle"})

        await self.push_frame(frame, direction)
