#!/usr/bin/env bash
set -euo pipefail

LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PEM="${EC2_PEM:-$HOME/.ssh/ec2-key.pem}"
REMOTE="${EC2_REMOTE:-ec2-user@<EC2_PUBLIC_IP>}"

if [[ "$REMOTE" == *"<EC2_PUBLIC_IP>"* ]]; then
  echo "Usage: EC2_PEM=/path/to/key.pem EC2_REMOTE=ec2-user@<IP> bash deploy/sync_to_ec2.sh"
  exit 1
fi

echo "=== Syncing Kisan Sahayak to $REMOTE:~/kisan-sahayak ==="
rsync -avz --delete \
  --exclude '.git' \
  --exclude 'node_modules' \
  --exclude '__pycache__' \
  --exclude '.venv*' \
  --exclude 'maya2-native' \
  --exclude 'logs' \
  --exclude 'data' \
  --exclude 'certs' \
  -e "ssh -i $PEM -o StrictHostKeyChecking=no" \
  "$LOCAL_DIR/" "$REMOTE:~/kisan-sahayak/"

echo "=== Sync complete! ==="
