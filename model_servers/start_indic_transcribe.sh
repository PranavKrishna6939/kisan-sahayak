#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export HF_TOKEN="${HF_TOKEN:-$(cat ~/.cache/huggingface/token 2>/dev/null || true)}"
export INDIC_TRANSCRIBE_MODEL="${INDIC_TRANSCRIBE_MODEL:-bodhan-ai/indic-transcribe-flex}"
export STT_PORT="${STT_PORT:-8002}"

exec "$ROOT_DIR/.venv-stt/bin/python" "$ROOT_DIR/model_servers/indic_transcribe_server.py"
