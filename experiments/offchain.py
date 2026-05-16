"""Local off-chain weight store (mirrors C++ data/offchain)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path("data/offchain")


def store_offchain(weights: list[float]) -> tuple[str, str]:
    ROOT.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(weights)
    h = hashlib.sha256(payload.encode()).hexdigest()
    path = ROOT / f"{h}.json"
    path.write_text(payload)
    return f"offchain://{h}", h


def load_offchain(ref: str) -> list[float]:
    key = ref.replace("offchain://", "")
    path = ROOT / f"{key}.json"
    return json.loads(path.read_text())
