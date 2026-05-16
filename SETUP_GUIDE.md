# CCFL Setup Guide

## 1. Dev container (required on macOS/Windows)

Reopen project in container (CCF 4.0.7-virtual). Build:

```bash
make build-virtual
```

## 2. Start CCF — choose platform

### Virtual (development)

```bash
make run-virtual
# Optional: more FL clients
make run-virtual SANDBOX_USERS=100
```

### SGX (real TEE)

```bash
make build-sgx
make run-sgx
```

Certificates appear under `.sandbox_ccf/`.

## 3. Run real FL (not simulated)

```bash
pip install -r requirements.txt
python -m experiments.runner.run_ccf_fl --platform virtual \
  --config experiments/config/mnist_iid.yaml
```

| Config | Method | What runs on CCF |
|--------|--------|------------------|
| `mnist_iid.yaml` | ccfl | AHDA |
| `ablation_fedavg_only.yaml` | fedavg | Plain FedAvg |
| `blockchain_fl_onchain.yaml` | blockchain_fl | FedAvg, weights on ledger only |
| `he_fedavg_mnist.yaml` | he_based | Paillier HE aggregate in CCF |
| `paper_full.yaml` | ccfl | 100 clients, 30 rounds |

## 4. Generate figures from real metrics

```bash
python experiments/plots/generate_figures.py
```

Results: `results/*/metrics.jsonl`, figures: `figures/`.
