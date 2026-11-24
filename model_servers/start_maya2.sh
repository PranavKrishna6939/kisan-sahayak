#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export HF_TOKEN="${HF_TOKEN:-$(cat ~/.cache/huggingface/token 2>/dev/null || true)}"

cd "$ROOT_DIR/maya2-native"
exec "$ROOT_DIR/.venv-maya2/bin/python" -m maya3.server \
  --ckpt maya-research/maya2-native \
  --host 127.0.0.1 \
  --port "${TTS_PORT:-8003}" \
  --max-seats "${MAYA_MAX_SEATS:-1}"
