from __future__ import annotations

import copy
from typing import Any

import numpy as np


def model_poisoning(weights: list[float], scale: float = 10.0) -> list[float]:
    return [w * scale for w in weights]


def byzantine_random(weights: list[float], rng: np.random.Generator) -> list[float]:
    return rng.normal(0, 5.0, size=len(weights)).tolist()


def label_flip(y: np.ndarray, num_classes: int) -> np.ndarray:
    return (y + 1) % num_classes


def apply_attack(
    attack: str,
    weights: list[float],
    y: np.ndarray | None = None,
    num_classes: int = 10,
    attack_strength: float = 1.0,
    rng: np.random.Generator | None = None,
) -> tuple[list[float], np.ndarray | None]:
    rng = rng or np.random.default_rng()
    w = copy.deepcopy(weights)
    y_out = y

    if attack == "none" or not attack:
        return w, y_out
    if attack == "model_poisoning":
        return model_poisoning(w, scale=1.0 + 9.0 * attack_strength), y_out
    if attack == "label_flip" and y is not None:
        return w, label_flip(y, num_classes)
    if attack == "byzantine":
        return byzantine_random(w, rng), y_out
    if attack == "sybil":
        return model_poisoning(w, scale=5.0), y_out
    return w, y_out
