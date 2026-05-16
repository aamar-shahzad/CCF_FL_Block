from __future__ import annotations

import json
from pathlib import Path


def mean_final_accuracy(metrics_path: Path) -> float:
    rounds: dict[int, float] = {}
    if not metrics_path.exists():
        return 0.0
    for line in metrics_path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        rounds[int(row["round"])] = float(row.get("accuracy", 0))
    return rounds[max(rounds)] if rounds else 0.0
