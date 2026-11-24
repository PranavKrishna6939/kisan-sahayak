"""Pipecat SegmentedSTTService backed by Bodhan AI Indic-Transcribe Flex (:8002)."""

from __future__ import annotations

import io
import time
import uuid
import wave
from typing import AsyncGenerator

import httpx
from loguru import logger
from pipecat.frames.frames import ErrorFrame, Frame, TranscriptionFrame
from pipecat.services.settings import STTSettings
from pipecat.services.stt_service import SegmentedSTTService

from backend.config import STT_URL
from backend.services.session_state import CallSessionState


def _ensure_wav_bytes(audio: bytes, sample_rate: int = 16000) -> bytes:
    """Pipecat SegmentedSTTService already wraps segments in a WAV header by default.
    Never double-wrap RIFF headers (which injects a loud pop and corrupts first syllables)."""
    if audio[:4] == b"RIFF":
        return audio
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio)
    return buf.getvalue()


class IndicTranscribeSTTService(SegmentedSTTService):
    """Utterance-segmented STT service calling local Bodhan AI Indic-Transcribe Flex."""

    def __init__(
        self,
        session: CallSessionState,
        stt_url: str = STT_URL,
        sample_rate: int = 16000,
        **kwargs,
    ):
        super().__init__(
            sample_rate=sample_rate,
            trailing_silence_secs=0.4,
            settings=STTSettings(model="bodhan-ai/indic-transcribe-flex", language="auto"),
            **kwargs,
        )
        self._session = session
        self._stt_url = stt_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=30.0)

    async def cleanup(self):
        await self._client.aclose()
        await super().cleanup()

    async def run_stt(self, audio: bytes) -> AsyncGenerator[Frame, None]:
        if not audio or len(audio) < 3200:  # < 100ms of 16kHz PCM16
            return

        wav_bytes = _ensure_wav_bytes(audio, sample_rate=self._sample_rate or 16000)
        lang_param = self._session.language_mode
        allow_all = lang_param == "auto_all"

        t0 = time.perf_counter()
        try:
            await self._session.send_ui_event({"type": "state", "state": "transcribing"})
            resp = await self._client.post(
                f"{self._stt_url}/transcribe",
                files={"audio": ("utterance.wav", wav_bytes, "audio/wav")},
                data={
                    "lang": lang_param,
                    "current_lang": self._session.detected_language,
                    "mode": "native",
                    "sample_rate": str(self._sample_rate or 16000),
                    "allow_all_langs": "true" if allow_all else "false",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.error(f"[{self._session.session_id}] Indic-Transcribe STT error: {exc}")
            await self._session.send_ui_event({"type": "state", "state": "idle"})
            yield ErrorFrame(error=f"STT error: {exc}")
            return

        text = (data.get("text") or "").strip()
        detected_lang = data.get("language") or self._session.detected_language
        confidence = float(data.get("confidence") or 1.0)
        switched = bool(data.get("switched"))
        stt_ms = int((time.perf_counter() - t0) * 1000)

        if not text:
            await self._session.send_ui_event({"type": "state", "state": "idle"})
            return

        logger.info(
            f"[{self._session.session_id}] STT ({detected_lang}, switched={switched}, "
            f"conf={confidence:.2f}, {stt_ms}ms, top3={data.get('topk', [])[:3]}): {text}"
        )

        msg_id = uuid.uuid4().hex[:10]
        entry = await self._session.append_transcript(
            role="user", text=text, language=detected_lang, msg_id=msg_id
        )
        # Update language state & refresh LLM system prompt AFTER appending user turn so stage advances!
        await self._session.set_detected_language(detected_lang, confidence=confidence)
        await self._session.send_ui_event({
            "type": "transcript",
            "message": entry,
            "latency_ms": {"stt": stt_ms},
        })
        await self._session.send_ui_event({"type": "state", "state": "thinking"})

        yield TranscriptionFrame(
            text=text,
            user_id="farmer",
            timestamp=str(time.time()),
        )
