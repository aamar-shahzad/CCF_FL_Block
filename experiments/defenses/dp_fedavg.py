from __future__ import annotations

import numpy as np


def add_gaussian_noise(weights: list[float], sigma: float = 0.01) -> list[float]:
    rng = np.random.default_rng()
    noise = rng.normal(0, sigma, size=len(weights))
    return [w + float(n) for w, n in zip(weights, noise)]
