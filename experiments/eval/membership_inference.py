#!/usr/bin/env python3
"""Post-hoc membership inference evaluation (shadow model, eval only)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def shadow_attack_score(confidences_member: list[float], confidences_nonmember: list[float]) -> float:
    """Simple threshold attack: members tend to have higher max softmax confidence."""
    if not confidences_member or not confidences_nonmember:
        return 0.5
    threshold = float(np.median(confidences_member + confidences_nonmember))
    tp = sum(1 for c in confidences_member if c >= threshold)
    tn = sum(1 for c in confidences_nonmember if c < threshold)
    return (tp + tn) / (len(confidences_member) + len(confidences_nonmember))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=Path("results"))
    parser.add_argument("--output", type=Path, default=Path("results/membership_inference.json"))
    args = parser.parse_args()

    member = [0.92, 0.88, 0.95, 0.91]
    nonmember = [0.55, 0.48, 0.62, 0.51]
    score = shadow_attack_score(member, nonmember)

    out = {
        "attack_accuracy": score,
        "note": "Placeholder shadow-model eval; replace with trained shadow model on real FL outputs.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
