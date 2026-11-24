"""FastAPI microservice wrapping Bodhan AI's Indic-Transcribe Flex (27 Indian languages + Sticky LID).

Loads `bodhan-ai/indic-transcribe-flex` in BF16 on CUDA and serves:
  - GET  /health
  - POST /transcribe   (WAV/PCM audio + optional lang, current_lang prior, mode)

Uses a single FastConformer encoder pass for both Language Identification (LID)
and transcription, applying a conversation-aware sticky prior so short replies
or low-confidence LID guesses never hijack the conversation into an unwanted language.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from typing import Optional

import numpy as np
import soundfile as sf
import torch
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from huggingface_hub import snapshot_download

logging.basicConfig(level=logging.INFO, format="%(asctime)s [STT] %(levelname)s %(message)s")
logger = logging.getLogger("indic_transcribe_server")

MODEL_ID = os.environ.get("INDIC_TRANSCRIBE_MODEL", "bodhan-ai/indic-transcribe-flex")
CORE_LID_LANGS = ("as", "bn", "en", "gu", "hi", "kn", "ml", "mr", "or", "pa", "ta", "te")

# Broad language-family grouping for short-utterance disambiguation
INDO_ARYAN = frozenset({"hi", "gu", "mr", "pa", "bn", "as", "or", "bho", "mai", "hne", "bgc", "bhb", "doi", "ne", "sa", "kok", "ur", "ks", "sd"})
DRAVIDIAN = frozenset({"ta", "te", "kn", "ml"})

asr_model = None
lid_fn = None
modes_map = None
gpu_lock = asyncio.Lock()


def _load_model():
    global asr_model, lid_fn, modes_map
    t0 = time.perf_counter()
    logger.info("Resolving Hugging Face snapshot for %s ...", MODEL_ID)
    model_dir = snapshot_download(MODEL_ID, ignore_patterns=["nemo/*", "*.png"])
    if model_dir not in sys.path:
        sys.path.insert(0, model_dir)
    from indic_transcribe import IndicTranscribe, MODES, lid_from_encoder_states  # type: ignore

    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.bfloat16 if device == "cuda" else torch.float32
    logger.info("Loading IndicTranscribe on %s (%s) ...", device, dtype)
    asr_model = IndicTranscribe.from_pretrained(model_dir, device=device, dtype=dtype, max_seconds=35.0)
    lid_fn = lid_from_encoder_states
    modes_map = MODES
    logger.info("IndicTranscribe loaded in %.2fs", time.perf_counter() - t0)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await asyncio.to_thread(_load_model)
    yield


app = FastAPI(title="Bodhan AI Indic-Transcribe Flex Service", lifespan=lifespan)


@app.get("/health")
async def health():
    return {
        "status": "ok" if asr_model is not None else "loading",
        "model": MODEL_ID,
        "device": asr_model.device if asr_model else None,
    }


def _decode_audio_bytes(raw: bytes, sample_rate: int = 16000) -> tuple[np.ndarray, int]:
    """Accept either WAV/FLAC bytes or raw 16-bit mono PCM bytes."""
    if raw[:4] in (b"RIFF", b"fLaC", b"OggS"):
        wav, sr = sf.read(io.BytesIO(raw), dtype="float32", always_2d=True)
        mono = wav.mean(axis=1)
        return mono, sr
    byte_len = len(raw) - (len(raw) % 2)
    pcm = np.frombuffer(raw[:byte_len], dtype=np.int16).astype(np.float32) / 32768.0
    return pcm, sample_rate


def _active_speech_seconds(wav: np.ndarray, sr: int = 16000) -> float:
    """Estimate active speech duration (excluding trailing/leading silence padding)."""
    if len(wav) == 0:
        return 0.0
    frame = int(sr * 0.02)  # 20ms frames
    n_frames = len(wav) // frame
    if n_frames == 0:
        return len(wav) / sr
    reshaped = wav[: n_frames * frame].reshape(n_frames, frame)
    frame_rms = np.sqrt(np.mean(reshaped ** 2, axis=1))
    peak = float(np.max(frame_rms))
    if peak < 0.004:
        return 0.0
    thresh = max(0.008, peak * 0.12)
    active_frames = int(np.sum(frame_rms >= thresh))
    return active_frames * 0.02


def _same_family(a: str, b: str) -> bool:
    if a == b:
        return True
    if a in INDO_ARYAN and b in INDO_ARYAN:
        return True
    if a in DRAVIDIAN and b in DRAVIDIAN:
        return True
    return False


def _choose_sticky_language(
    topk: list[tuple[str, float]],
    current_lang: Optional[str],
    speech_secs: float,
) -> tuple[str, float, bool]:
    """Decide target decode language using a conversation-aware sticky prior.

    Returns (chosen_lang, confidence, switched).
    """
    if not topk:
        return (current_lang or "hi", 0.0, False)

    top_lang, top_prob = topk[0][0], float(topk[0][1])
    if not current_lang:
        return (top_lang, top_prob, False)

    if top_lang == current_lang:
        return (current_lang, top_prob, False)

    probs = {lang: float(p) for lang, p in topk}
    cur_prob = probs.get(current_lang, 0.0)
    ratio = top_prob / max(cur_prob, 1e-4)

    # Short 1-3 word utterances (< 1.8s) are highly ambiguous across related Indian languages
    if speech_secs < 1.8:
        # Only switch on very short clips if cross-family & overwhelming certainty
        if (not _same_family(top_lang, current_lang)) and top_prob >= 0.96 and cur_prob < 0.02:
            return (top_lang, top_prob, True)
        return (current_lang, max(cur_prob, 0.5), False)

    # Full utterances (>= 1.8s): require strong evidence before switching languages mid-call
    min_prob = 0.92 if _same_family(top_lang, current_lang) else 0.88
    if top_prob >= min_prob and cur_prob < 0.08 and ratio >= 12.0:
        return (top_lang, top_prob, True)

    return (current_lang, max(cur_prob, 0.5), False)


def _transcribe_sync(
    wav: np.ndarray,
    sr: int,
    lang: Optional[str],
    current_lang: Optional[str],
    mode: str,
    allow_all_langs: bool,
) -> dict:
    assert asr_model is not None and lid_fn is not None and modes_map is not None

    if sr != 16000:
        import torchaudio

        wav_t = torch.from_numpy(wav)
        wav = torchaudio.functional.resample(wav_t, sr, 16000).numpy()

    duration_s = len(wav) / 16000.0
    speech_s = _active_speech_seconds(wav, 16000)
    rms = float(np.sqrt(np.mean(wav ** 2))) if len(wav) > 0 else 0.0
    if duration_s < 0.18 or speech_s < 0.12 or rms < 0.0025:
        return {
            "text": "",
            "language": current_lang or (lang if lang not in (None, "auto", "auto_all") else "hi"),
            "confidence": 0.0,
            "duration_ms": int(duration_s * 1000),
            "speech_ms": int(speech_s * 1000),
            "latency_ms": 0,
            "switched": False,
            "topk": [],
        }

    # Trim safely to 29.5s to respect the 30s FastConformer training window
    max_samples = int(29.5 * 16000)
    if len(wav) > max_samples:
        wav = wav[-max_samples:]

    t0 = time.perf_counter()
    explicit_lang = None if (not lang or lang in ("auto", "auto_all")) else lang
    allowed = None if (explicit_lang or allow_all_langs or lang == "auto_all") else CORE_LID_LANGS
    itn, romanized = modes_map.get(mode, (False, False))

    feats, mask = asr_model._features(torch.as_tensor(wav, dtype=torch.float32))

    with torch.inference_mode():
        # Single encoder pass shared by LID + conditional decoding
        enc = asr_model.model.model.encoder(feats, attention_mask=mask)
        topk = lid_fn(
            asr_model.model,
            enc.last_hidden_state,
            enc.lengths,
            tokenizer=asr_model.tokenizer,
            topk=12 if allowed else 27,
            allowed_langs=allowed,
        )[0]

        if explicit_lang:
            chosen_lang = explicit_lang
            conf = 1.0
            switched = False
        else:
            chosen_lang, conf, switched = _choose_sticky_language(
                topk=topk,
                current_lang=current_lang,
                speech_secs=speech_s,
            )

        prompt = asr_model.tokenizer.encode_prompt(chosen_lang, itn=itn, romanized=romanized)
        ids = torch.tensor([prompt], device=asr_model.device)
        out = asr_model.model.generate(
            encoder_outputs=enc,
            attention_mask=mask,
            decoder_input_ids=ids,
            max_new_tokens=384,
        )
        text = asr_model.tokenizer.decode(
            asr_model.tokenizer.strip_prompt_and_trim(out[0].tolist(), prompt)
        )

    latency_ms = int((time.perf_counter() - t0) * 1000)
    clean_text = (text or "").strip()
    top4 = [[str(k), round(float(v), 4)] for k, v in topk[:4]]

    logger.info(
        "STT chosen=%s (switched=%s, prior=%s, speech=%.2fs, %dms) raw_top3=%s -> %r",
        chosen_lang,
        switched,
        current_lang,
        speech_s,
        latency_ms,
        top4[:3],
        clean_text,
    )

    return {
        "text": clean_text,
        "language": chosen_lang,
        "confidence": round(float(conf), 4),
        "duration_ms": int(duration_s * 1000),
        "speech_ms": int(speech_s * 1000),
        "latency_ms": latency_ms,
        "switched": switched,
        "topk": top4,
    }


@app.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    lang: Optional[str] = Form(default="auto"),
    current_lang: Optional[str] = Form(default=""),
    mode: str = Form(default="native"),
    sample_rate: int = Form(default=16000),
    allow_all_langs: bool = Form(default=False),
):
    if asr_model is None:
        raise HTTPException(status_code=503, detail="STT model is still loading")

    raw = await audio.read()
    if not raw:
        return {
            "text": "",
            "language": current_lang or "hi",
            "confidence": 0.0,
            "duration_ms": 0,
            "speech_ms": 0,
            "latency_ms": 0,
            "switched": False,
            "topk": [],
        }

    wav, sr = _decode_audio_bytes(raw, sample_rate=sample_rate)
    prior = current_lang.strip() if current_lang else None
    async with gpu_lock:
        result = await asyncio.to_thread(_transcribe_sync, wav, sr, lang, prior, mode, allow_all_langs)
    return result


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("STT_PORT", "8002"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
