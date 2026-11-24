"""End-to-end verification script for Kisan Sahayak (unit + live EC2 pipeline tests)."""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

import httpx
import websockets

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import detect_script_language, map_to_tts_language
from backend.schemas.loan_application import (
    LoanApplication,
    compute_completion,
    compute_recommended_schemes,
)


def run_unit_tests() -> None:
    print("=== [1/4] Unit Tests: Schema, Scheme Engine & Script Detection ===")
    app = LoanApplication()
    changed = app.apply_patch({
        "full_name": "Ramesh Yadav",
        "village": "Rampur",
        "district": "Varanasi",
        "total_land_acres": "4 acres",
        "kharif_crops": "Paddy",
        "rabi_crops": "Wheat",
        "pm_kisan_beneficiary": "Yes",
        "allied_activities": "2 buffaloes",
        "amount_required_inr": "150000",
        "unknown_field": "should_be_ignored",
    })
    assert "full_name" in changed and "unknown_field" not in changed
    comp = compute_completion(app)
    assert comp["core_filled"] >= 7 and comp["percent"] > 30
    schemes = [s["id"] for s in compute_recommended_schemes(app)]
    assert "pm-kisan-kcc" in schemes
    assert "kcc-miss" in schemes
    assert "kcc-allied" in schemes
    assert "pmfby" in schemes

    assert detect_script_language("नमस्ते किसान भाई") == "hi"
    assert detect_script_language("नमस्कार शेतकरी दादा", fallback="mr") == "mr"
    assert detect_script_language("வணக்கம் விவசாயி") == "ta"
    assert detect_script_language("నమస్కారం రైతు") == "te"
    assert detect_script_language("নমস্কার") == "bn"
    assert detect_script_language("Hello farmer") == "en"
    assert map_to_tts_language("bho") == "hi"
    assert map_to_tts_language("hne") == "hi"
    assert map_to_tts_language("kok") == "mr"
    print("  Unit tests PASSED!")


async def run_live_model_tests() -> None:
    print("\n=== [2/4] Live Health Check (:8000 /api/health) ===")
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get("http://127.0.0.1:8000/api/health")
        r.raise_for_status()
        health = r.json()
        print("  Health:", json.dumps(health, indent=2))
        assert health["status"] == "ok", f"Stack not healthy: {health}"

        print("\n=== [3/4] Round-Trip TTS (Maya 2 Native) -> STT (Indic-Transcribe Flex) ===")
        for lang, sentence in [
            ("hi", "मेरा नाम रमेश यादव है और मेरे पास चार एकड़ जमीन है।"),
            ("ta", "என் பெயர் முருகன், எனக்கு மூன்று ஏக்கர் நிலம் உள்ளது."),
            ("en", "I need a Kisan Credit Card loan of two lakh rupees."),
        ]:
            t0 = time.perf_counter()
            tts_r = await client.post(
                "http://127.0.0.1:8003/v1/audio/speech",
                json={
                    "model": "maya3",
                    "input": sentence,
                    "language": lang,
                    "voice": "Vaidehi",
                    "response_format": "wav",
                    "normalize": True,
                },
            )
            tts_r.raise_for_status()
            wav_bytes = tts_r.content
            tts_ms = int((time.perf_counter() - t0) * 1000)

            t1 = time.perf_counter()
            stt_r = await client.post(
                "http://127.0.0.1:8002/transcribe",
                files={"audio": ("test.wav", wav_bytes, "audio/wav")},
                data={"lang": "auto", "mode": "native"},
            )
            stt_r.raise_for_status()
            stt_data = stt_r.json()
            stt_ms = int((time.perf_counter() - t1) * 1000)
            print(
                f"  [{lang}] TTS={tts_ms}ms ({len(wav_bytes)}B) -> "
                f"STT={stt_ms}ms detected={stt_data['language']} text={stt_data['text']!r}"
            )
            assert len(wav_bytes) > 5000
            assert len(stt_data["text"].strip()) > 3


async def run_live_websocket_pipeline_test() -> None:
    print("\n=== [4/4] Live Pipecat WebSocket Call: Hindi Turn -> Form Extraction -> Tamil Switch ===")
    uri = "ws://127.0.0.1:8000/ws/call?mode=outbound&voice=Vaidehi&lang=auto&greeting_lang=hi"
    async with websockets.connect(uri, max_size=16 * 1024 * 1024) as ws:
        greeting_audio_bytes = 0
        got_init = False
        got_greeting_text = False

        # Wait up to 15s for session_init + greeting transcript + initial TTS audio
        deadline = time.time() + 18.0
        while time.time() < deadline:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=1.5)
            except asyncio.TimeoutError:
                if got_init and got_greeting_text and greeting_audio_bytes > 4000:
                    break
                continue
            if isinstance(msg, bytes):
                greeting_audio_bytes += len(msg)
            else:
                ev = json.loads(msg)
                t = ev.get("type")
                if t == "session_init":
                    got_init = True
                elif t == "transcript" and ev["message"]["role"] == "assistant":
                    got_greeting_text = True
                    print("  Greeting:", ev["message"]["text"][:90], "...")
                elif t == "state" and ev.get("state") == "idle" and greeting_audio_bytes > 0:
                    break

        print(f"  Greeting audio received: {greeting_audio_bytes} bytes (24kHz PCM16)")
        assert got_init and got_greeting_text and greeting_audio_bytes > 4000

        # Turn 1: Farmer replies in Hindi with rich loan details
        turn1 = (
            "मेरा नाम रमेश यादव है, पिता का नाम रामलाल यादव। मैं वाराणसी जिले के रामपुर गांव, "
            "उत्तर प्रदेश से बोल रहा हूं। मेरे पास 4 एकड़ अपनी जमीन है जिसमें ट्यूबवेल से सिंचाई होती है। "
            "मैं गेहूं और धान उगाता हूं और मुझे डेढ़ लाख रुपये का नया किसान क्रेडिट कार्ड लोन चाहिए।"
        )
        await ws.send(json.dumps({"type": "text_input", "text": turn1}))

        reply1_text = ""
        reply1_audio = 0
        form_app = {}
        deadline = time.time() + 30.0
        while time.time() < deadline:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
            except asyncio.TimeoutError:
                if reply1_text and reply1_audio > 4000 and form_app.get("full_name"):
                    break
                continue
            if isinstance(msg, bytes):
                reply1_audio += len(msg)
            else:
                ev = json.loads(msg)
                t = ev.get("type")
                if t == "transcript_done" and ev["message"]["role"] == "assistant":
                    reply1_text = ev["message"]["text"]
                    print("  Agent Turn 1 (Hindi):", reply1_text)
                elif t == "form_update":
                    form_app = ev["application"]
                    print(
                        f"  Live Form Update ({ev['completion']['percent']}%): changed={ev['changed_fields']}"
                    )

        assert reply1_text and "<think>" not in reply1_text
        assert reply1_audio > 4000
        assert form_app.get("full_name"), f"Expected full_name extracted, got: {form_app}"
        assert form_app.get("village") or form_app.get("district"), f"Expected location, got: {form_app}"

        # Turn 2: Mid-call language switch to Tamil + PM-KISAN & dairy cattle info
        turn2 = "நான் தமிழ்நாட்டில் இருந்து பேசுகிறேன். எனக்கு PM-KISAN கிடைக்கிறது மற்றும் இரண்டு மாடுகள் உள்ளன."
        await ws.send(json.dumps({"type": "text_input", "text": turn2}))

        reply2_text = ""
        reply2_audio = 0
        deadline = time.time() + 30.0
        while time.time() < deadline:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
            except asyncio.TimeoutError:
                if reply2_text and reply2_audio > 4000:
                    break
                continue
            if isinstance(msg, bytes):
                reply2_audio += len(msg)
            else:
                ev = json.loads(msg)
                t = ev.get("type")
                if t == "transcript_done" and ev["message"]["role"] == "assistant":
                    reply2_text = ev["message"]["text"]
                    print("  Agent Turn 2 (Tamil switch):", reply2_text)
                elif t == "form_update":
                    form_app = ev["application"]
                    print(
                        f"  Live Form Update 2 ({ev['completion']['percent']}%): changed={ev['changed_fields']}"
                    )

        assert reply2_text and "<think>" not in reply2_text
        assert detect_script_language(reply2_text) == "ta", f"Expected Tamil reply, got: {reply2_text}"
        assert reply2_audio > 4000
        print("  Final extracted fields:", {k: v for k, v in form_app.items() if v})
        print("\nALL LIVE PIPELINE TESTS PASSED!")


async def main():
    run_unit_tests()
    if "--live" in sys.argv:
        await run_live_model_tests()
        await run_live_websocket_pipeline_test()


if __name__ == "__main__":
    asyncio.run(main())
