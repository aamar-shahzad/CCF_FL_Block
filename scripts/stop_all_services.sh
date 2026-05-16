#!/usr/bin/env bash
# Stop CCF sandbox, UI/API, and anything bound to FL ports.
set -euo pipefail
WORKSPACE_DIR="$(cd "$(dirname "$0")/.." && pwd)"

kill_port() {
  local port=$1
  if command -v fuser &>/dev/null; then
    fuser -k "${port}/tcp" 2>/dev/null || true
  fi
  if command -v lsof &>/dev/null; then
    local pids
    pids=$(lsof -ti:"$port" 2>/dev/null || true)
    [ -n "$pids" ] && kill -9 $pids 2>/dev/null || true
  fi
}

echo "Stopping CCF / proxy processes..."
pkill -f "start_network.py.*liblskv" 2>/dev/null || true
pkill -f "/opt/ccf_virtual/bin/sandbox.sh" 2>/dev/null || true
pkill -f "ccf_virtual/bin/cchost" 2>/dev/null || true
pkill -f "proxy_server.py" 2>/dev/null || true
sleep 1

kill_port 8000
kill_port 5000
kill_port 8080
sleep 1

echo "Done. Ports 8000, 5000, 8080 should be free."
