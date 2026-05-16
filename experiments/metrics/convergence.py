from __future__ import annotations

import json
from pathlib import Path


def rounds_to_threshold(metrics_path: Path, threshold: float = 0.95) -> int | None:
    if not metrics_path.exists():
        return None
    max_acc = 0.0
    series: list[tuple[int, float]] = []
    for line in metrics_path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        acc = float(row.get("accuracy", 0))
        max_acc = max(max_acc, acc)
        series.append((int(row["round"]), acc))
    target = threshold * max_acc
    for rnd, acc in sorted(series):
        if acc >= target:
            return rnd
    return None
