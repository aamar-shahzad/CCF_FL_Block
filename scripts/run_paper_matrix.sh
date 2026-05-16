#!/usr/bin/env bash
# Run a subset of the paper evaluation matrix (requires CCF sandbox running).
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate 2>/dev/null || true

DATASETS=(mnist fashion_mnist cifar10 har)
METHODS=(ccfl fedavg multi_krum dp_fedavg)
DIST=(iid non_iid)
MAL=(0.0 0.4)

for ds in "${DATASETS[@]}"; do
  for method in "${METHODS[@]}"; do
    for dist in "${DIST[@]}"; do
      for mf in "${MAL[@]}"; do
        echo "=== $ds $method $dist malicious=$mf ==="
        python -m experiments.runner.run_ccf_fl --platform auto --config /dev/stdin <<EOF
dataset: $ds
method: $method
num_clients: 10
rounds: 5
distribution: $dist
malicious_frac: $mf
attack: model_poisoning
offchain: true
seed: 42
EOF
      done
    done
  done
done

python experiments/plots/generate_figures.py
