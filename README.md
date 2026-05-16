# CCFL — Confidential Consortium Federated Learning

Real implementation on **Microsoft CCF** (virtual and SGX): AHDA aggregation, vote-mediated client access, hybrid off-chain storage, and paper-aligned CNN models.

## Architecture

| Component | Implementation |
|-----------|----------------|
| Ledger / consensus | CCF (real, not simulated) |
| CCFL defense | AHDA in C++ (`method=ahda`) |
| FedAvg / Multi-Krum | CCF `method=fedavg` / `method=krum` |
| Blockchain-FL baseline | FedAvg with **on-chain-only** weights (`offchain: false`) |
| HE baseline | **Paillier** homomorphic sum in CCF (`method=he`) |
| FL models | Paper CNN (MNIST/Fashion-MNIST), CIFAR-10 CNN, HAR MLP |

## Build (Linux dev container only)

```bash
# Reopen in Container → .devcontainer/
make build-virtual   # virtual mode
make build-sgx       # SGX enclave (hardware required to run)
```

See [BUILD.md](BUILD.md).

## Run

**Terminal 1 — CCF network:**

```bash
make run-virtual          # insecure virtual (development)
# or
make run-sgx              # SGX enclave (production TEE)
```

**Terminal 2 — FL experiment:**

```bash
source .venv/bin/activate
pip install -r requirements.txt

# CCFL (AHDA) on virtual sandbox
python -m experiments.runner.run_ccf_fl --platform virtual \
  --config experiments/config/mnist_iid.yaml

# Same on SGX
python -m experiments.runner.run_ccf_fl --platform sgx \
  --config experiments/config/mnist_iid.yaml

# Baselines (all real on CCF)
python -m experiments.runner.run_ccf_fl --config experiments/config/blockchain_fl_onchain.yaml
python -m experiments.runner.run_ccf_fl --config experiments/config/he_fedavg_mnist.yaml
```

## Models (paper / FL_Clients.ipynb)

- **MNIST / Fashion-MNIST:** Conv2D(64)→Pool→Conv2D(32)→Pool→Dense(10)
- **CIFAR-10:** 3-layer CNN + BatchNorm
- **HAR:** MLP 561→256→128→classes

Defined in [`experiments/models/paper_models.py`](experiments/models/paper_models.py).

## API

| Endpoint | Description |
|----------|-------------|
| `PUT .../aggregate_weights_local?method=ahda\|fedavg\|krum\|he` | Real aggregation in enclave |
| `POST .../register_client` | Vote-mediated enrollment |
| `GET .../aggregate_stats` | AHDA round statistics |

## 100-client runs

```bash
make run-virtual SANDBOX_USERS=100
python -m experiments.runner.run_ccf_fl --config experiments/config/paper_full.yaml
```
