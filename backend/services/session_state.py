"""Shared per-call session state bridging Pipecat processors, WebSocket UI events, and SQLite."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable, Optional

from loguru import logger
from pipecat.processors.aggregators.llm_context import LLMContext

from backend.config import (
    VOICES,
    get_language_display,
    load_prompt,
    map_to_tts_language,
)
from backend.database import save_session_state
from backend.schemas.loan_application import (
    LoanApplication,
    compute_completion,
    compute_conversation_stage,
    compute_recommended_schemes,
    format_form_for_prompt,
    format_plain_text_document,
)

VOICE_PROMPT_TEMPLATE = load_prompt("voice_agent_system.md")


@dataclass
class CallSessionState:
    session_id: str
    call_mode: str = "outbound"           # "outbound" | "inbound"
    voice: str = "Vaidehi"
    language_mode: str = "auto"           # "auto" | "auto_all" | specific 2/3-letter code
    detected_language: str = "hi"
    application: LoanApplication = field(default_factory=LoanApplication)
    transcript: list[dict[str, Any]] = field(default_factory=list)
    send_text_fn: Optional[Callable[[str], Awaitable[None]]] = None
    llm_context: Optional[LLMContext] = None
    bot_speaking: bool = False
    current_assistant_msg_id: Optional[str] = None
    current_assistant_buffer: str = ""
    _ws_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _save_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def send_ui_event(self, payload: dict[str, Any]) -> None:
        if not self.send_text_fn:
            return
        try:
            async with self._ws_lock:
                await self.send_text_fn(json.dumps(payload, ensure_ascii=False))
        except Exception as exc:
            logger.debug(f"[{self.session_id}] Failed to send UI event {payload.get('type')}: {exc}")

    def build_system_prompt(self) -> str:
        lang_info = get_language_display(self.detected_language)
        collected, missing = format_form_for_prompt(self.application)
        stage_name, stage_instruction = compute_conversation_stage(
            self.application, self.transcript
        )
        voice_meta = next((v for v in VOICES if v["id"].lower() == self.voice.lower()), None)
        agent_gender = voice_meta["gender"] if voice_meta else "female"
        return VOICE_PROMPT_TEMPLATE.format(
            detected_language_label=lang_info["label"],
            detected_language_code=lang_info["code"],
            agent_gender=agent_gender,
            call_mode=self.call_mode,
            conversation_stage=stage_name,
            stage_instruction=stage_instruction,
            form_state_summary=collected,
            next_priority_fields=missing,
        )

    def refresh_llm_system_prompt(self) -> None:
        """Keep the first system message in LLMContext synchronized with live form & language."""
        if not self.llm_context:
            return
        prompt_text = self.build_system_prompt()
        msgs = self.llm_context.get_messages()
        if msgs and msgs[0].get("role") == "system":
            msgs[0]["content"] = prompt_text
        else:
            msgs.insert(0, {"role": "system", "content": prompt_text})

    def get_tts_language(self) -> str:
        if self.language_mode not in ("auto", "auto_all"):
            return map_to_tts_language(self.language_mode)
        return map_to_tts_language(self.detected_language)

    async def set_detected_language(self, lang_code: str, confidence: float = 1.0) -> None:
        if not lang_code:
            return
        changed = lang_code != self.detected_language
        self.detected_language = lang_code
        lang_info = get_language_display(lang_code)
        # Auto-record preferred language in application if not manually overridden
        if not self.application.preferred_language or changed:
            self.application.preferred_language = lang_info["name"]
        self.refresh_llm_system_prompt()
        await self.send_ui_event({
            "type": "language_detected",
            "language": lang_info,
            "confidence": confidence,
        })

    async def append_transcript(
        self,
        role: str,
        text: str,
        language: Optional[str] = None,
        msg_id: Optional[str] = None,
        interrupted: bool = False,
    ) -> dict[str, Any]:
        entry = {
            "id": msg_id or uuid.uuid4().hex[:10],
            "role": role,
            "text": text,
            "language": get_language_display(language or self.detected_language),
            "timestamp": time.time(),
            "interrupted": interrupted,
        }
        self.transcript.append(entry)
        return entry

    async def emit_form_update(self, changed_fields: list[str] | None = None) -> None:
        self.refresh_llm_system_prompt()
        payload = {
            "type": "form_update",
            "application": self.application.model_dump(),
            "changed_fields": changed_fields or [],
            "completion": compute_completion(self.application),
            "recommended_schemes": compute_recommended_schemes(self.application),
            "plain_text": format_plain_text_document(self.application),
        }
        await self.send_ui_event(payload)
        await self.persist()

    async def persist(self) -> None:
        try:
            async with self._save_lock:
                await save_session_state(
                    self.session_id,
                    self.application.model_dump(),
                    self.transcript,
                    self.detected_language,
                )
        except Exception as exc:
            logger.warning(f"[{self.session_id}] Failed to persist session: {exc}")
