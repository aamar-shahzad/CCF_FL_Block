from __future__ import annotations

import json
from pathlib import Path


def total_onchain_bytes(metrics_path: Path) -> int:
    total = 0
    if not metrics_path.exists():
        return 0
    for line in metrics_path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        total = max(total, int(row.get("onchain_bytes", 0)))
    return total
