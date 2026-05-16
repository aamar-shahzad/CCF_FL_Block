"""Map experiment method names to real CCF aggregation endpoints."""

from __future__ import annotations

# All methods run on CCF — no simulated latency.
METHOD_MAP = {
    "ccfl": "ahda",
    "ahda": "ahda",
    "fedavg": "fedavg",
    "multi_krum": "krum",
    "krum": "krum",
    "dp_fedavg": "fedavg",
    # Blockchain-FL baseline: full weights on CCF ledger (no off-chain store).
    "blockchain_fl": "fedavg",
    "onchain": "fedavg",
    # HE baseline: Paillier ciphertext aggregation inside CCF.
    "he_based": "he",
    "he_fedavg": "he",
    "he": "he",
}


def resolve_ccf_method(method: str) -> str:
    return METHOD_MAP.get(method.lower(), "ahda")


def use_offchain(method: str, config_default: bool = True) -> bool:
    """Blockchain-FL comparison uses on-chain-only weight storage."""
    if method.lower() in ("blockchain_fl", "onchain"):
        return False
    return config_default
