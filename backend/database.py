"""Async SQLite persistence for farmer call sessions, transcripts, and loan profiles."""

from __future__ import annotations

import json
import time
from typing import Any, Optional

import aiosqlite

from backend.config import DB_PATH


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                call_mode TEXT NOT NULL,
                voice TEXT NOT NULL,
                detected_language TEXT NOT NULL DEFAULT 'hi',
                application_json TEXT NOT NULL DEFAULT '{}',
                transcript_json TEXT NOT NULL DEFAULT '[]',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        await db.commit()


async def create_session(session_id: str, call_mode: str, voice: str, language: str = "hi") -> None:
    now = time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO sessions
            (id, call_mode, voice, detected_language, application_json, transcript_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, '{}', '[]', ?, ?)
            """,
            (session_id, call_mode, voice, language, now, now),
        )
        await db.commit()


async def save_session_state(
    session_id: str,
    application: dict[str, Any],
    transcript: list[dict[str, Any]],
    detected_language: str,
) -> None:
    now = time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE sessions
            SET application_json = ?, transcript_json = ?, detected_language = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                json.dumps(application, ensure_ascii=False),
                json.dumps(transcript, ensure_ascii=False),
                detected_language,
                now,
                session_id,
            ),
        )
        await db.commit()


async def list_sessions(limit: int = 25) -> list[dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, call_mode, voice, detected_language, application_json, created_at, updated_at FROM sessions ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ) as cur:
            rows = await cur.fetchall()
            out = []
            for r in rows:
                app_data = json.loads(r["application_json"] or "{}")
                out.append({
                    "id": r["id"],
                    "call_mode": r["call_mode"],
                    "voice": r["voice"],
                    "detected_language": r["detected_language"],
                    "farmer_name": app_data.get("full_name"),
                    "village": app_data.get("village"),
                    "loan_purpose": app_data.get("loan_purpose"),
                    "amount_required_inr": app_data.get("amount_required_inr"),
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                })
            return out


async def get_session(session_id: str) -> Optional[dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)) as cur:
            r = await cur.fetchone()
            if not r:
                return None
            return {
                "id": r["id"],
                "call_mode": r["call_mode"],
                "voice": r["voice"],
                "detected_language": r["detected_language"],
                "application": json.loads(r["application_json"] or "{}"),
                "transcript": json.loads(r["transcript_json"] or "[]"),
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
