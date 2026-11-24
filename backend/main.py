"""FastAPI server for Kisan Sahayak — WebSocket voice calls, field-agent API, and React UI."""

from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from backend.config import (
    FRONTEND_DIST_DIR,
    LANGUAGES,
    LLM_MODEL,
    OLLAMA_BASE_URL,
    SPEECH_CONFIG,
    STT_URL,
    TTS_HTTP_URL,
    VOICES,
)
from backend.database import get_session, init_db, list_sessions
from backend.pipeline import run_voice_call
from backend.schemas.loan_application import (
    LoanApplication,
    compute_completion,
    compute_recommended_schemes,
    format_plain_text_document,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()
    logger.info("Kisan Sahayak backend initialized.")
    yield


app = FastAPI(title="Kisan Sahayak — Multilingual Voice AI Agricultural Credit System", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _probe_http(url: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(url)
            return {"ok": r.status_code == 200, "status": r.status_code}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@app.get("/api/health")
async def api_health():
    stt = await _probe_http(f"{STT_URL}/health")
    tts = await _probe_http(f"{TTS_HTTP_URL}/health")
    llm = await _probe_http(f"{OLLAMA_BASE_URL}/api/version")
    all_ok = stt["ok"] and tts["ok"] and llm["ok"]
    return {
        "status": "ok" if all_ok else "degraded",
        "services": {
            "stt_indic_transcribe": stt,
            "tts_maya2_native": tts,
            "llm_qwen35_9b": {**llm, "model": LLM_MODEL},
            "vad_silero": {"ok": True, "runtime": "in-process CPU"},
        },
    }


@app.get("/api/config")
async def api_config():
    return {
        "voices": VOICES,
        "default_voice": SPEECH_CONFIG["tts"]["default_voice"],
        "languages": LANGUAGES,
        "models": {
            "stt": SPEECH_CONFIG["stt"]["model_id"],
            "llm": f"Qwen/Qwen3.5-9B ({LLM_MODEL})",
            "tts": SPEECH_CONFIG["tts"]["model_id"],
            "vad": "Silero VAD (Pipecat)",
        },
    }


@app.get("/api/sessions")
async def api_list_sessions(limit: int = 25):
    return {"sessions": await list_sessions(limit=limit)}


@app.get("/api/sessions/{session_id}")
async def api_get_session(session_id: str):
    row = await get_session(session_id)
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    app_model = LoanApplication(**row["application"])
    return {
        **row,
        "completion": compute_completion(app_model),
        "recommended_schemes": compute_recommended_schemes(app_model),
        "plain_text": format_plain_text_document(app_model),
    }


@app.get("/api/sessions/{session_id}/export")
async def api_export_session(session_id: str, fmt: str = Query(default="json")):
    row = await get_session(session_id)
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    app_model = LoanApplication(**row["application"])
    if fmt == "txt":
        return PlainTextResponse(
            format_plain_text_document(app_model),
            headers={"Content-Disposition": f'attachment; filename="kisan-application-{session_id}.txt"'},
        )
    return JSONResponse(
        content={
            "session_id": session_id,
            "call_mode": row["call_mode"],
            "detected_language": row["detected_language"],
            "application": row["application"],
            "recommended_schemes": compute_recommended_schemes(app_model),
            "completion": compute_completion(app_model),
            "transcript": row["transcript"],
        },
        headers={"Content-Disposition": f'attachment; filename="kisan-application-{session_id}.json"'},
    )


@app.websocket("/ws/call")
async def ws_call(
    websocket: WebSocket,
    mode: str = Query(default="outbound"),
    voice: str = Query(default="Vaidehi"),
    lang: str = Query(default="auto"),
    greeting_lang: str = Query(default="hi"),
):
    await websocket.accept()
    try:
        await run_voice_call(
            websocket=websocket,
            call_mode=mode,
            voice=voice,
            language_mode=lang,
            greeting_lang=greeting_lang,
        )
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected.")
    except Exception as exc:
        logger.exception(f"WebSocket voice call error: {exc}")


# Serve compiled React frontend when built
if FRONTEND_DIST_DIR.exists():
    assets_dir = FRONTEND_DIST_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        candidate = FRONTEND_DIST_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(FRONTEND_DIST_DIR / "index.html"))
