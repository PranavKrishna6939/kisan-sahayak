"""Pipecat 1.17.0 real-time cascaded voice pipeline for Kisan Sahayak."""

from __future__ import annotations

import asyncio
import uuid

from fastapi import WebSocket
from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import TTSSpeakFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.processors.audio.vad_processor import VADProcessor
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)

from backend.config import (
    GREETINGS,
    LANGUAGES,
    LLM_API_KEY,
    LLM_MODEL,
    LLM_OPENAI_BASE_URL,
    SPEECH_CONFIG,
    VOICES,
    get_language_display,
)
from backend.database import create_session
from backend.schemas.loan_application import (
    compute_completion,
    compute_recommended_schemes,
    format_plain_text_document,
)
from backend.services.form_extractor import (
    InputEventAndExtractorProcessor,
    OutputTranscriptProcessor,
)
from backend.services.indic_transcribe_stt import IndicTranscribeSTTService
from backend.services.maya2_tts import Maya2TTSService
from backend.services.protocol import KisanWebSocketSerializer
from backend.services.session_state import CallSessionState


async def run_voice_call(
    websocket: WebSocket,
    call_mode: str = "outbound",
    voice: str = "Vaidehi",
    language_mode: str = "auto",
    greeting_lang: str = "hi",
) -> None:
    """Attach a live Pipecat voice pipeline to an accepted FastAPI WebSocket."""
    session_id = uuid.uuid4().hex[:12]
    initial_lang = greeting_lang if greeting_lang in ("hi", "en") else "hi"
    if language_mode not in ("auto", "auto_all"):
        initial_lang = language_mode

    session = CallSessionState(
        session_id=session_id,
        call_mode=call_mode if call_mode in ("inbound", "outbound") else "outbound",
        voice=voice or SPEECH_CONFIG["tts"]["default_voice"],
        language_mode=language_mode,
        detected_language=initial_lang,
        send_text_fn=websocket.send_text,
    )
    await create_session(session_id, session.call_mode, session.voice, session.detected_language)

    vad_cfg = SPEECH_CONFIG["vad"]
    vad_analyzer = SileroVADAnalyzer(
        params=VADParams(
            confidence=float(vad_cfg["confidence"]),
            start_secs=float(vad_cfg["start_secs"]),
            stop_secs=float(vad_cfg["stop_secs"]),
            min_volume=float(vad_cfg["min_volume"]),
        )
    )
    vad_processor = VADProcessor(vad_analyzer=vad_analyzer)

    serializer = KisanWebSocketSerializer(
        session=session, in_sample_rate=16000, out_sample_rate=24000
    )
    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_in_sample_rate=16000,
            audio_out_enabled=True,
            audio_out_sample_rate=24000,
            add_wav_header=False,
            serializer=serializer,
        ),
    )

    stt = IndicTranscribeSTTService(session=session, sample_rate=16000)

    llm = OpenAILLMService(
        api_key=LLM_API_KEY,
        base_url=LLM_OPENAI_BASE_URL,
        settings=OpenAILLMService.Settings(
            model=LLM_MODEL,
            temperature=0.45,
            frequency_penalty=0.35,
            presence_penalty=0.25,
            max_tokens=220,
            extra={"reasoning_effort": "none"},
        ),
    )

    tts = Maya2TTSService(session=session, sample_rate=24000)

    # Seed initial conversation context
    greeting_key = "en" if initial_lang == "en" else "hi"
    greeting_text = GREETINGS[session.call_mode][greeting_key]

    context = LLMContext(
        messages=[
            {"role": "system", "content": session.build_system_prompt()},
            {"role": "assistant", "content": greeting_text},
        ]
    )
    session.llm_context = context

    context_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(),
    )

    input_bridge = InputEventAndExtractorProcessor(session=session)
    output_bridge = OutputTranscriptProcessor(session=session)

    pipeline = Pipeline(
        [
            transport.input(),
            vad_processor,
            stt,
            input_bridge,
            context_aggregator.user(),
            llm,
            output_bridge,
            tts,
            transport.output(),
            context_aggregator.assistant(),
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=16000,
            audio_out_sample_rate=24000,
            enable_metrics=True,
        ),
    )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(_transport, _client):
        logger.info(
            f"[{session_id}] Call connected (mode={session.call_mode}, voice={session.voice}, lang={session.language_mode})"
        )
        # Send initial session state & form schema snapshot
        await session.send_ui_event(
            {
                "type": "session_init",
                "session_id": session_id,
                "call_mode": session.call_mode,
                "voice": session.voice,
                "language_mode": session.language_mode,
                "detected_language": get_language_display(session.detected_language),
                "application": session.application.model_dump(),
                "completion": compute_completion(session.application),
                "recommended_schemes": compute_recommended_schemes(session.application),
                "plain_text": format_plain_text_document(session.application),
                "voices": VOICES,
                "languages": LANGUAGES,
            }
        )

        # Deliver immediate opening greeting via Maya 2 Native TTS + left transcript pane
        entry = await session.append_transcript(
            role="assistant", text=greeting_text, language=greeting_key
        )
        await session.send_ui_event({"type": "transcript", "message": entry})
        await session.persist()
        await asyncio.sleep(0.15)
        await task.queue_frames([TTSSpeakFrame(text=greeting_text)])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(_transport, _client):
        logger.info(f"[{session_id}] Client disconnected.")
        await session.persist()
        await task.cancel()

    runner = PipelineRunner(handle_sigint=False)
    try:
        await runner.run(task)
    finally:
        await session.persist()
        logger.info(f"[{session_id}] Call session closed cleanly.")
