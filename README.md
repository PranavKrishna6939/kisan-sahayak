# Kisan Sahayak — Multilingual Voice AI Agricultural Credit System

An empathetic, language-agnostic voice AI calling system built for Indian farmers—including illiterate and low-literacy callers—to educate them about Indian agricultural credit & insurance schemes (KCC 4% MISS, PM-KISAN Fast-Track KCC, Agri-Term / Farm Mechanization Loans, AIF, Animal Husbandry & Fisheries KCC, PMFBY) and conversationally prepare a unified bank loan application in real time for independent field-agent follow-up.

## Cascade Voice Architecture

- **Orchestrator**: [Pipecat 1.17](https://github.com/pipecat-ai/pipecat) (`FastAPIWebsocketTransport` + `VADProcessor` + `SegmentedSTTService` + `OpenAILLMService` + `TTSService`)
- **VAD & Barge-In**: **Silero VAD** (in-process CPU) + browser speaking-state echo gate (`AudioWorklet`) + instant `InterruptionFrame` cancellation across LLM, Maya 2 Native WS (`{"type":"cancel"}`), and 24 kHz browser ring buffer (`<1 ms` flush)
- **STT (ASR + Sticky LID)**: **Bodhan AI Indic-Transcribe Flex** (`bodhan-ai/indic-transcribe-flex`, 27 Indian languages + English, single-pass FastConformer encoder with conversation-aware sticky language prior, `:8002`)
- **LLM (Voice + Parallel Form Extractor)**: **Qwen3.5-9B** (4-bit via Ollama `kisan-qwen35` with `num_ctx: 12288`, non-thinking mode `reasoning_effort="none"` / `think=false`, `:11434`)
- **TTS (Streaming 24 kHz)**: **Maya 2 Native** (`maya-research/maya2-native` via `maya3.server` WS `/v1/tts/stream`, 12 languages, 6 curated Indian voices, `:8003`)
- **Frontend**: Minimal 3-pane React + TypeScript + Tailwind UI:
  1. **Left Pane**: Live two-sided call transcript with native script, per-utterance language badges, and optional text input.
  2. **Center Pane**: Inbound / Outbound call toggle, audio-reactive Voice Orb / Mic button, Mute / Interrupt / End controls, and live matched scheme cards.
  3. **Right Pane**: Real-time updating 40-field unified agricultural loan application (synthesized from Bank of India Form AG-100, SBI PM-KISAN KCC, and Axis Bank Kisan Power PDFs in `docs/reference_forms/`) with structured form & live plain-text views, manual edit sync, and JSON export.

## Repository Layout

```text
kisan-sahayak/
├── backend/
│   ├── config.py                     # Service URLs, 27->12 language map & Unicode script detector
│   ├── database.py                   # Async SQLite persistence for sessions & leads
│   ├── main.py                       # FastAPI server (WS /ws/call, REST /api/*, static SPA)
│   ├── pipeline.py                   # Pipecat 1.17 cascaded pipeline wiring
│   ├── requirements.txt
│   ├── prompts/
│   │   ├── voice_agent_system.md     # 6-stage credit-scheme-first empathetic voice prompt
│   │   ├── form_extractor_system.md  # Real-time multilingual JSON delta extractor prompt
│   │   └── speech_config.yaml        # Silero VAD params, 27-lang map, Maya 2 voices & greetings
│   ├── schemas/
│   │   └── loan_application.py       # Unified 40-field schema, stage tracker & scheme engine
│   ├── services/
│   │   ├── indic_transcribe_stt.py   # Pipecat SegmentedSTTService -> Indic-Transcribe Flex
│   │   ├── maya2_tts.py              # Pipecat TTSService -> Maya 2 Native WS streaming
│   │   ├── form_extractor.py         # Parallel async Qwen3.5-9B extractor + UI event bridge
│   │   ├── protocol.py               # Multiplexed PCM16 binary + JSON WebSocket serializer
│   │   └── session_state.py          # Shared per-call state & dynamic prompt refresh
│   └── tests/
│       └── test_e2e.py               # Unit + live TTS/STT/WebSocket end-to-end tests
├── model_servers/
│   ├── indic_transcribe_server.py    # FastAPI wrapper for bodhan-ai/indic-transcribe-flex
│   ├── requirements-stt.txt
│   ├── start_maya2.sh
│   ├── start_indic_transcribe.sh
│   └── start_all.sh                  # Sequential VRAM-safe boot (fits on 1x 24 GB NVIDIA A10G)
├── frontend/                         # Vite + React + TypeScript + Tailwind CSS 3-pane UI
├── deploy/
│   └── sync_to_ec2.sh                # rsync deployment helper
└── docs/
    └── reference_forms/              # Source Bank of India, SBI, and Axis Bank loan PDFs
```

## Hardware & VRAM Footprint (Single 24 GB NVIDIA A10G)

| Service | Model | Steady VRAM |
| :--- | :--- | :---: |
| TTS (`:8003`) | `maya-research/maya2-native` (`max_seats=1`) | ~7.7 GiB |
| LLM (`:11434`) | `Qwen/Qwen3.5-9B` (4-bit Ollama, `num_ctx=12288`) | ~6.9 GiB |
| STT (`:8002`) | `bodhan-ai/indic-transcribe-flex` (BF16) | ~2.7 GiB |
| VAD & Orchestrator | Silero VAD + Pipecat + FastAPI | CPU |
| **Total** | | **~17.3 / 23.0 GiB** |

## Quick Setup (Linux GPU Server)

1. **Authenticate Hugging Face** (for gated repos `maya-research/maya2-native` and `bodhan-ai/indic-transcribe-flex`):
   ```bash
   export HF_TOKEN=<YOUR_HUGGINGFACE_TOKEN>
   ```
2. **Create isolated Python 3.12 environments with `uv`**:
   ```bash
   # Maya 2 Native TTS
   git clone https://github.com/MayaResearch/maya2-native maya2-native
   uv venv .venv-maya2 --python 3.12
   uv pip install --python .venv-maya2/bin/python --upgrade "packaging>=24.2" "setuptools>=77" wheel
   uv pip install --python .venv-maya2/bin/python --no-build-isolation --index-strategy unsafe-best-match \
     --extra-index-url https://download.pytorch.org/whl/cu128 -e "./maya2-native[server]"

   # Bodhan AI Indic-Transcribe Flex STT
   uv venv .venv-stt --python 3.12
   uv pip install --python .venv-stt/bin/python torch torchaudio --index-url https://download.pytorch.org/whl/cu128
   uv pip install --python .venv-stt/bin/python -r model_servers/requirements-stt.txt

   # Pipecat Backend
   uv venv .venv-backend --python 3.12
   uv pip install --python .venv-backend/bin/python -r backend/requirements.txt
   ```
3. **Install Ollama & pull `qwen3.5:9b`**:
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ollama pull qwen3.5:9b
   ```
4. **Build the React frontend**:
   ```bash
   cd frontend && npm install && npm run build && cd ..
   ```
5. **Start the full stack**:
   ```bash
   bash model_servers/start_all.sh
   ```

## Accessing the Web Interface
Browsers require HTTPS or `localhost` for microphone capture (`getUserMedia`):
- **Direct HTTPS**: `https://<EC2_PUBLIC_IP>:8091` (accept the self-signed certificate once)
- **SSH Tunnel**: `ssh -i <key.pem> -L 8000:localhost:8000 ec2-user@<EC2_PUBLIC_IP>` → open `http://localhost:8000`
