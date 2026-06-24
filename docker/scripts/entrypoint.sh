#!/bin/bash
set -e

echo "=== SenseVoice-API ==="
echo "Device: ${DEVICE}"
echo "Model:  ${MODEL_ID}"
echo "Port:   ${PORT:-10095}"
echo "========================="

exec python -m uvicorn api.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-10095}" \
    --log-level info \
    --timeout-keep-alive 65
