#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR" "$ROOT_DIR/certs" "$ROOT_DIR/data"

chmod +x "$ROOT_DIR"/model_servers/*.sh

echo "=== Stopping any previous Kisan Sahayak processes ==="
pkill -f "maya3.server" 2>/dev/null || true
pkill -f "indic_transcribe_server.py" 2>/dev/null || true
pkill -f "backend/main.py" 2>/dev/null || true
pkill -f "uvicorn backend.main:app" 2>/dev/null || true
ollama stop qwen3.5:9b 2>/dev/null || true
sleep 2

wait_for_url() {
  local name="$1"
  local url="$2"
  local max_wait="${3:-180}"
  echo -n "Waiting for $name ($url)..."
  for ((i=0; i<max_wait; i++)); do
    if curl -sf "$url" >/dev/null 2>&1; then
      echo " READY (${i}s)"
      return 0
    fi
    sleep 1
  done
  echo " FAILED (timeout after ${max_wait}s)"
  return 1
}

echo "=== [1/4] Starting Maya 2 Native TTS (:8003) ==="
nohup "$ROOT_DIR/model_servers/start_maya2.sh" > "$LOG_DIR/maya2.log" 2>&1 &
wait_for_url "Maya 2 Native TTS" "http://127.0.0.1:8003/health" 240

echo "=== [2/4] Starting Bodhan AI Indic-Transcribe Flex STT (:8002) ==="
nohup "$ROOT_DIR/model_servers/start_indic_transcribe.sh" > "$LOG_DIR/stt.log" 2>&1 &
wait_for_url "Indic-Transcribe STT" "http://127.0.0.1:8002/health" 180

echo "=== [3/4] Ensuring Ollama kisan-qwen35 (Qwen3.5-9B, 12K ctx) (:11434) is warm ==="
sudo systemctl start ollama 2>/dev/null || (pgrep -x ollama >/dev/null || nohup ollama serve > "$LOG_DIR/ollama.log" 2>&1 &)
wait_for_url "Ollama" "http://127.0.0.1:11434/api/version" 30
cat > /tmp/Modelfile.kisan-qwen35 << 'EOF'
FROM qwen3.5:9b
PARAMETER num_ctx 12288
PARAMETER repeat_penalty 1.15
PARAMETER repeat_last_n 128
EOF
ollama create kisan-qwen35 -f /tmp/Modelfile.kisan-qwen35 >/dev/null
ollama stop qwen3.5:9b 2>/dev/null || true
# Warm kisan-qwen35 into VRAM with keep_alive=24h so it stays resident
curl -sf http://127.0.0.1:11434/api/chat \
  -H "Content-Type: application/json" \
  -d '{"model":"kisan-qwen35","messages":[{"role":"user","content":"Hi"}],"think":false,"stream":false,"keep_alive":"24h"}' >/dev/null
echo "kisan-qwen35 warmed in VRAM."

echo "=== [4/4] Generating self-signed TLS cert (if needed) & starting Pipecat Backend ==="
PUBLIC_IP="${PUBLIC_IP:-$(curl -sf --max-time 2 http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo '127.0.0.1')}"
if [ ! -f "$ROOT_DIR/certs/cert.pem" ] || [ ! -f "$ROOT_DIR/certs/key.pem" ]; then
  openssl req -x509 -newkey rsa:2048 -nodes \
    -keyout "$ROOT_DIR/certs/key.pem" \
    -out "$ROOT_DIR/certs/cert.pem" \
    -days 365 \
    -subj "/CN=${PUBLIC_IP}" \
    -addext "subjectAltName=IP:${PUBLIC_IP},DNS:localhost" 2>/dev/null
fi

cd "$ROOT_DIR"
# HTTP on :8000 (for SSH tunnel http://localhost:8000)
nohup "$ROOT_DIR/.venv-backend/bin/uvicorn" backend.main:app \
  --host 127.0.0.1 --port 8000 --log-level info \
  > "$LOG_DIR/backend_http.log" 2>&1 &

# HTTPS on :8091 (for direct browser mic access over HTTPS)
nohup "$ROOT_DIR/.venv-backend/bin/uvicorn" backend.main:app \
  --host 0.0.0.0 --port 8091 \
  --ssl-keyfile "$ROOT_DIR/certs/key.pem" \
  --ssl-certfile "$ROOT_DIR/certs/cert.pem" \
  --log-level info \
  > "$LOG_DIR/backend_https.log" 2>&1 &

wait_for_url "Pipecat Backend HTTP (:8000)" "http://127.0.0.1:8000/api/health" 45

echo ""
echo "=== GPU Memory Breakdown ==="
nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv
echo ""
echo "Kisan Sahayak is LIVE!"
echo "  - Direct HTTPS:  https://${PUBLIC_IP}:8091  (accept self-signed cert once)"
echo "  - SSH Tunnel:    ssh -i <path-to-key.pem> -L 8000:localhost:8000 ec2-user@${PUBLIC_IP}"
echo "                   then open http://localhost:8000"
