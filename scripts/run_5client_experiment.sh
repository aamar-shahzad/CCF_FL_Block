#!/usr/bin/env bash
# Run a 5-client CCFL experiment (CCF sandbox must be up with >= 5 users).
set -euo pipefail
cd "$(dirname "$0")/.."

CONFIG="${1:-experiments/config/mnist_5clients_ccfl.yaml}"
if [[ "${2:-}" == "--imagenet" ]]; then
  CONFIG="experiments/config/fashion_mnist_5clients_imagenet.yaml"
fi

echo "=== Config: $CONFIG ==="
echo "=== Checking CCF on https://127.0.0.1:8000 ==="
if ! curl -sk --max-time 3 -o /dev/null https://127.0.0.1:8000/; then
  echo "CCF is not running. Start it in another terminal:"
  echo "  make run-virtual SANDBOX_USERS=5"
  exit 1
fi

CERT_DIR="workspace/sandbox_common"
if [[ ! -f "$CERT_DIR/member0_cert.pem" ]]; then
  echo "Missing certs in $CERT_DIR — start CCF sandbox first."
  exit 1
fi
if [[ ! -f "$CERT_DIR/user4_cert.pem" ]]; then
  echo "Need at least 5 sandbox users (user0..user4 certs)."
  echo "Restart CCF:  make run-virtual SANDBOX_USERS=5"
  exit 1
fi

source .venv/bin/activate
export CCF_WORKSPACE="$PWD/$CERT_DIR"
export CCF_URL="${CCF_URL:-https://127.0.0.1:8000/app}"

pip install -q -r requirements.txt 2>/dev/null || true

echo "=== Running experiment ==="
python -m experiments.runner.run_ccf_fl --platform virtual --config "$CONFIG"

echo "=== Done. Metrics under results/ ==="
