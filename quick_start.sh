#!/usr/bin/env bash
# CCFL quick start — run inside Linux dev container.
set -euo pipefail
cd "$(dirname "$0")"

echo "=== Build CCF app (virtual) ==="
make build-virtual

echo "=== Start CCF sandbox (background) ==="
echo "Run in another terminal: make run-virtual"
echo ""
echo "=== Then run FL experiment ==="
echo "  source .venv/bin/activate"
echo "  pip install -r requirements.txt"
echo "  python -m experiments.runner.run_ccf_fl --platform virtual --config experiments/config/mnist_iid.yaml"
echo ""
echo "=== SGX (requires SGX hardware + build-sgx) ==="
echo "  make run-sgx   # terminal 1"
echo "  make run-fl-sgx   # terminal 2"
