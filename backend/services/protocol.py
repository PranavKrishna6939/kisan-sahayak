"""Custom Pipecat FrameSerializer multiplexing raw PCM16 audio & JSON UI control messages."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Optional

from loguru import logger
from pipecat.frames.frames import (
    Frame,
    InputAudioRawFrame,
    InterruptionFrame,
    OutputAudioRawFrame,
    TranscriptionFrame,
)
from pipecat.serializers.base_serializer import FrameSerializer

from backend.config import detect_script_language
from backend.services.session_state import CallSessionState


class KisanWebSocketSerializer(FrameSerializer):
    """Binary frames = raw PCM16 mono audio (16 kHz in / 24 kHz out); Text frames = JSON events."""

    def __init__(
        self,
        session: CallSessionState,
        in_sample_rate: int = 16000,
        out_sample_rate: int = 24000,
    ):
        super().__init__()
        self._session = session
        self._in_sr = in_sample_rate
        self._out_sr = out_sample_rate

    async def serialize(self, frame: Frame) -> str | bytes | None:
        if isinstance(frame, OutputAudioRawFrame):
            return frame.audio
        if isinstance(frame, InterruptionFrame):
            return json.dumps({"type": "interrupt"})
        return None

    async def deserialize(self, data: str | bytes) -> Optional[Frame]:
        if isinstance(data, (bytes, bytearray)):
            if not data:
                return None
            return InputAudioRawFrame(
                audio=bytes(data),
                sample_rate=self._in_sr,
                num_channels=1,
            )

        if isinstance(data, str):
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                return None

            mtype = msg.get("type")
            if mtype == "text_input":
                text = (msg.get("text") or "").strip()
                if not text:
                    return None
                lang = (
                    self._session.language_mode
                    if self._session.language_mode not in ("auto", "auto_all")
                    else detect_script_language(text, fallback=self._session.detected_language)
                )
                entry = await self._session.append_transcript(
                    role="user", text=text, language=lang, msg_id=uuid.uuid4().hex[:10]
                )
                await self._session.set_detected_language(lang, confidence=1.0)
                await self._session.send_ui_event({"type": "transcript", "message": entry})
                await self._session.send_ui_event({"type": "state", "state": "thinking"})
                return TranscriptionFrame(
                    text=text,
                    user_id="farmer",
                    timestamp=str(time.time()),
                )

            if mtype == "manual_form_edit":
                field = msg.get("field")
                value = msg.get("value")
                if field and hasattr(self._session.application, field):
                    setattr(self._session.application, field, (str(value).strip() or None))
                    asyncio.create_task(self._session.emit_form_update(changed_fields=[field]))
                return None

            if mtype == "set_voice":
                voice = (msg.get("voice") or "").strip()
                if voice:
                    self._session.voice = voice
                    logger.info(f"[{self._session.session_id}] Voice switched -> {voice}")
                return None

            if mtype == "set_language":
                lang = (msg.get("language") or "auto").strip()
                self._session.language_mode = lang
                if lang not in ("auto", "auto_all"):
                    await self._session.set_detected_language(lang, confidence=1.0)
                logger.info(f"[{self._session.session_id}] Language mode -> {lang}")
                return None

            if mtype == "interrupt":
                return InterruptionFrame()

        return None
