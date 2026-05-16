"""Thin wrapper for FL_Clients.ipynb — run MNIST IID experiment via harness."""
import subprocess
import sys

if __name__ == "__main__":
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "experiments.runner.run_ccf_fl",
            "--config",
            "experiments/config/mnist_iid.yaml",
        ]
    )
