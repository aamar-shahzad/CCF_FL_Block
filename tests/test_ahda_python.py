"""Python replication of AHDA threshold logic for CI without C++ build."""

import numpy as np


def sign_bit_signature(weights: np.ndarray) -> np.ndarray:
    bits = (weights >= 0).astype(np.uint8)
    return bits


def mean_hamming_distances(sigs: list[np.ndarray]) -> list[float]:
    n = len(sigs)
    out = []
    for i in range(n):
        d = []
        for j in range(n):
            if i == j:
                continue
            d.append(np.mean(sigs[i] != sigs[j]))
        out.append(float(np.mean(d)) if d else 0.0)
    return out


def test_outlier_rejected():
    honest = [np.full(32, 0.1) for _ in range(5)]
    outlier = np.full(32, 100.0)
    updates = honest + [outlier]
    sigs = [sign_bit_signature(u) for u in updates]
    dists = mean_hamming_distances(sigs)
    med = float(np.median(dists))
    mad = float(np.median(np.abs(np.array(dists) - med)))
    threshold = med + 2.5 * mad
    rejected = [i for i, d in enumerate(dists) if d > threshold]
    assert 5 in rejected
