from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class MetricsLogger:
    def __init__(self, run_id: str, root: Path = Path("results")):
        self.run_dir = root / run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.run_dir / "metrics.jsonl"

    def log(self, record: dict[str, Any]) -> None:
        record["ts"] = time.time()
        with self.path.open("a") as f:
            f.write(json.dumps(record) + "\n")
