#!/usr/bin/env bash
# Start CCF FL web UI. Works inside dev container; Mac browser needs port 8080 published.
set -e
cd "$(dirname "$0")"
PORT="${PROXY_PORT:-8080}"
ROOT="$(cd .. && pwd)"
PY="${ROOT}/.venv/bin/python3"
[[ -x "$PY" ]] || PY=python3

echo "=============================================="
echo " CCF FL UI"
echo "=============================================="
echo " Inside container:  http://127.0.0.1:${PORT}"
echo ""
echo " Mac / host browser:  http://localhost:${PORT}"
echo " (requires devcontainer rebuild so docker-compose publishes ports)"
echo " Inside Cursor only:  Cmd+Shift+P -> Simple Browser -> http://127.0.0.1:${PORT}"
echo "=============================================="
export PROXY_PORT="$PORT"
exec "$PY" proxy_server.py
