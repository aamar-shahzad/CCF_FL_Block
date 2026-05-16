"""Select TensorFlow or NumPy FL backend (auto-fallback when TF cannot load)."""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Any, Dict, Optional


def tensorflow_available() -> bool:
    if os.environ.get("FORCE_NUMPY_FL") == "1":
        return False
    try:
        r = subprocess.run(
            [sys.executable, "-c", "import tensorflow as tf; print(tf.__version__)"],
            capture_output=True,
            text=True,
            timeout=90,
        )
        return r.returncode == 0
    except Exception:
        return False


def resolve_backend(cfg: Optional[Dict[str, Any]] = None) -> str:
    cfg = cfg or {}
    explicit = (cfg.get("fl_backend") or os.environ.get("FL_BACKEND") or "auto").lower()
    if explicit == "numpy":
        return "numpy"
    if explicit == "tensorflow":
        if not tensorflow_available():
            raise RuntimeError(
                "fl_backend=tensorflow but TensorFlow cannot load (AVX required on this CPU). "
                "Use fl_backend: numpy in your config or rebuild devcontainer as arm64."
            )
        return "tensorflow"
    return "tensorflow" if tensorflow_available() else "numpy"


def get_client_module(cfg: Optional[Dict[str, Any]] = None):
    backend = resolve_backend(cfg)
    if backend == "numpy":
        from experiments.clients import numpy_client as client

        print(f"[CCFL] Using NumPy FL backend (no TensorFlow — AVX-safe)")
        return client
    from experiments.clients import tensorflow_client as client

    print(f"[CCFL] Using TensorFlow FL backend")
    return client
