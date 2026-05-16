#!/usr/bin/env python3
"""Run paper evaluation matrix and regenerate figures."""

from __future__ import annotations

import itertools
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run_config(cfg: dict) -> int:
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        import yaml

        yaml.dump(cfg, f)
        path = f.name
    cmd = [
        sys.executable,
        "-m",
        "experiments.runner.run_ccf_fl",
        "--config",
        path,
        "--platform",
        "auto",
    ]
    print("Running:", cfg.get("dataset"), cfg.get("method"), cfg.get("distribution"))
    return subprocess.call(cmd, cwd=str(ROOT))


def main() -> None:
    datasets = ["mnist", "fashion_mnist", "cifar10", "har"]
    methods = ["ccfl", "fedavg", "multi_krum", "dp_fedavg", "blockchain_fl", "he_based"]
    distributions = ["iid", "non_iid"]
    malicious_fracs = [0.0, 0.2, 0.4]
    attacks = ["none", "model_poisoning"]

    failures = 0
    for ds, method, dist, mf, atk in itertools.product(
        datasets, methods, distributions, malicious_fracs, attacks
    ):
        if mf == 0.0 and atk != "none":
            continue
        cfg = {
            "dataset": ds,
            "method": method,
            "num_clients": 10,
            "rounds": 5,
            "distribution": dist,
            "malicious_frac": mf,
            "attack": atk,
            "local_epochs": 1,
            "register_clients": method == "ccfl",
            "offchain": True,
            "seed": 42,
        }
        if ds == "cifar10":
            cfg["partitioned"] = True
        rc = run_config(cfg)
        if rc != 0:
            failures += 1
            print(f"Warning: run failed (exit {rc}), is CCF sandbox up?")

    subprocess.check_call(
        [sys.executable, str(ROOT / "experiments/plots/generate_figures.py")],
        cwd=str(ROOT),
    )
    print(f"Batch complete. Failures: {failures}")


if __name__ == "__main__":
    main()
