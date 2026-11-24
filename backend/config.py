"""Configuration loader for Kisan Sahayak voice AI system."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
PROMPTS_DIR = BACKEND_DIR / "prompts"
FRONTEND_DIST_DIR = ROOT_DIR / "frontend" / "dist"
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Service URLs
STT_URL = os.environ.get("STT_URL", "http://127.0.0.1:8002")
TTS_WS_URL = os.environ.get("TTS_WS_URL", "ws://127.0.0.1:8003/v1/tts/stream")
TTS_HTTP_URL = os.environ.get("TTS_HTTP_URL", "http://127.0.0.1:8003")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
LLM_OPENAI_BASE_URL = os.environ.get("LLM_OPENAI_BASE_URL", f"{OLLAMA_BASE_URL}/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "kisan-qwen35")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "ollama")

DB_PATH = Path(os.environ.get("DB_PATH", str(DATA_DIR / "kisan_sahayak.db")))


def load_speech_config() -> dict[str, Any]:
    with open(PROMPTS_DIR / "speech_config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_prompt(filename: str) -> str:
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


SPEECH_CONFIG: dict[str, Any] = load_speech_config()
LANGUAGES: dict[str, dict[str, str]] = SPEECH_CONFIG["languages"]
VOICES: list[dict[str, str]] = SPEECH_CONFIG["tts"]["voices"]
GREETINGS: dict[str, dict[str, str]] = SPEECH_CONFIG["greetings"]


def detect_script_language(text: str, fallback: str = "hi") -> str:
    """Fast Unicode script detector to ensure Maya 2 Native always gets a matching language tag."""
    counts: dict[str, int] = {
        "hi": 0,  # Devanagari (Hindi / Marathi / dialects)
        "bn": 0,  # Bengali / Assamese
        "ta": 0,  # Tamil
        "te": 0,  # Telugu
        "gu": 0,  # Gujarati
        "kn": 0,  # Kannada
        "ml": 0,  # Malayalam
        "pa": 0,  # Gurmukhi
        "or": 0,  # Odia
        "en": 0,  # Latin
    }
    for ch in text:
        cp = ord(ch)
        if 0x0900 <= cp <= 0x097F:
            counts["hi"] += 1
        elif 0x0980 <= cp <= 0x09FF:
            counts["bn"] += 1
        elif 0x0B80 <= cp <= 0x0BFF:
            counts["ta"] += 1
        elif 0x0C00 <= cp <= 0x0C7F:
            counts["te"] += 1
        elif 0x0A80 <= cp <= 0x0AFF:
            counts["gu"] += 1
        elif 0x0C80 <= cp <= 0x0CFF:
            counts["kn"] += 1
        elif 0x0D00 <= cp <= 0x0D7F:
            counts["ml"] += 1
        elif 0x0A00 <= cp <= 0x0A7F:
            counts["pa"] += 1
        elif 0x0B00 <= cp <= 0x0B7F:
            counts["or"] += 1
        elif ("a" <= ch <= "z") or ("A" <= ch <= "Z"):
            counts["en"] += 1

    best_lang, best_count = max(counts.items(), key=lambda kv: kv[1])
    if best_count == 0:
        return map_to_tts_language(fallback)

    # Preserve Marathi when Devanagari is detected and fallback is Marathi/Konkani
    if best_lang == "hi" and fallback in ("mr", "kok"):
        return "mr"
    # Preserve Assamese when Bengali-Assamese script is detected and fallback is Assamese
    if best_lang == "bn" and fallback == "as":
        return "as"
    return best_lang


def map_to_tts_language(lang_code: str) -> str:
    """Map any of the 27 Indic-Transcribe language codes to Maya 2 Native's 12 supported codes."""
    info = LANGUAGES.get(lang_code)
    if info:
        return info["tts_lang"]
    return "hi"


def get_language_display(lang_code: str) -> dict[str, str]:
    info = LANGUAGES.get(lang_code, {"name": "Hindi", "native": "हिन्दी", "tts_lang": "hi"})
    return {
        "code": lang_code,
        "name": info["name"],
        "native": info["native"],
        "tts_lang": info["tts_lang"],
        "label": f"{info['name']} ({info['native']})" if info["name"] != info["native"] else info["name"],
    }
