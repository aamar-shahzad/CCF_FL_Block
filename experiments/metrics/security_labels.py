from __future__ import annotations

import json
from pathlib import Path


def attack_success_rate(metrics_path: Path, baseline_acc: float = 0.9) -> float:
    """Lower final accuracy vs baseline => higher attack success."""
    if not metrics_path.exists():
        return 0.0
    last_acc = 0.0
    for line in metrics_path.read_text().splitlines():
        if line.strip():
            last_acc = float(json.loads(line).get("accuracy", 0))
    drop = max(0.0, baseline_acc - last_acc)
    return min(1.0, drop / baseline_acc)


def qualitative_rating(success_rate: float) -> str:
    if success_rate < 0.15:
        return "High"
    if success_rate < 0.35:
        return "Medium"
    return "Low"
