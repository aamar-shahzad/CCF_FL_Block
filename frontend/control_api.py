"""Backend control plane: status, sandbox cleanup, experiment runner."""

from __future__ import annotations

import json
import os
import re

import yaml
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
VENV_PYTHON = WORKSPACE_DIR / ".venv" / "bin" / "python3"
CONFIG_DIR = WORKSPACE_DIR / "experiments" / "config"
RESULTS_DIR = WORKSPACE_DIR / "results"
def _normalize_ccf_app_url(url: str) -> str:
    u = url.rstrip("/")
    while u.endswith("/app/app"):
        u = u[: -len("/app")]
    if not u.endswith("/app"):
        u = f"{u}/app"
    return u


def _ccf_node_url(url: str) -> str:
    u = url.rstrip("/")
    return u[: -len("/app")] if u.endswith("/app") else u


CCF_URL = _ccf_node_url(os.environ.get("CCF_URL", "https://127.0.0.1:8000"))
CCF_APP_URL = _normalize_ccf_app_url(os.environ.get("CCF_URL", "https://127.0.0.1:8000"))

_lock = threading.Lock()
_experiment_proc: Optional[subprocess.Popen] = None
_experiment_log: List[str] = []
_experiment_meta: Dict[str, Any] = {}


def _python() -> str:
    if VENV_PYTHON.is_file():
        return str(VENV_PYTHON)
    return sys.executable


def clean_sandbox() -> Dict[str, Any]:
    """Remove stale CCF sandbox node dirs (fixes missing 0.pem errors)."""
    removed: List[str] = []
    workspace = WORKSPACE_DIR / "workspace"
    if workspace.is_dir():
        for child in workspace.iterdir():
            if child.name.startswith("sandbox_") and child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
                removed.append(str(child))
    return {"ok": True, "removed": removed}


def check_ccf() -> Dict[str, Any]:
    import requests

    try:
        r = requests.get(
            f"{CCF_URL}/",
            verify=False,
            timeout=3,
        )
        return {"up": True, "status_code": r.status_code, "url": CCF_URL}
    except Exception as exc:
        return {"up": False, "error": str(exc), "url": CCF_URL}


def check_certs(min_users: int = 5) -> Dict[str, Any]:
    from experiments.ccf_client import count_user_certs

    cert_dir = WORKSPACE_DIR / "workspace" / "sandbox_common"
    if not (cert_dir / "member0_cert.pem").is_file():
        return {"ok": False, "cert_dir": str(cert_dir), "missing": ["member0_cert.pem"]}
    user_count = count_user_certs(cert_dir)
    missing = []
    for i in range(min(min_users, user_count + 1)):
        name = f"user{i}_cert.pem"
        if not (cert_dir / name).is_file():
            missing.append(name)
    return {
        "ok": len(missing) == 0 and user_count >= min_users,
        "cert_dir": str(cert_dir),
        "missing": missing,
        "min_users": min_users,
        "user_count": user_count,
    }


def _config_arg(cfg: Path) -> str:
    try:
        return str(cfg.relative_to(WORKSPACE_DIR))
    except ValueError:
        return str(cfg)


def _ccf_method_name(method: str) -> str:
    from experiments.defenses.methods import resolve_ccf_method

    return resolve_ccf_method(method)


def _effective_offchain(method: str, meta: Dict[str, Any]) -> bool:
    from experiments.defenses.methods import use_offchain

    return use_offchain(method, bool(meta.get("offchain", True)))


def _training_backend_label(meta: Dict[str, Any]) -> str:
    backend = str(meta.get("fl_backend", "auto")).lower()
    if backend == "numpy":
        return "NumPy (linear softmax, no TensorFlow)"
    if backend == "tensorflow":
        return "TensorFlow/Keras"
    return "Auto (NumPy if no AVX, else TensorFlow)"


def list_configs() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not CONFIG_DIR.is_dir():
        return out
    for path in sorted(CONFIG_DIR.glob("*.yaml")):
        meta: Dict[str, Any] = {}
        try:
            with path.open() as f:
                meta = yaml.safe_load(f) or {}
        except Exception:
            pass
        method = str(meta.get("method", ""))
        attack = str(meta.get("attack", "none") or "none")
        malicious_frac = float(meta.get("malicious_frac", 0.0) or 0.0)
        offchain = _effective_offchain(method, meta)
        entry = {
            "id": path.name,
            "path": f"experiments/config/{path.name}",
            "dataset": meta.get("dataset", ""),
            "method": method,
            "ccf_method": _ccf_method_name(method),
            "num_clients": meta.get("num_clients"),
            "sandbox_users": meta.get("sandbox_users"),
            "rounds": meta.get("rounds"),
            "local_epochs": meta.get("local_epochs"),
            "distribution": meta.get("distribution", "iid"),
            "alpha": meta.get("alpha"),
            "attack": attack,
            "attack_strength": meta.get("attack_strength"),
            "malicious_frac": malicious_frac,
            "has_attack": attack not in ("", "none") and malicious_frac > 0,
            "fl_backend": meta.get("fl_backend", "auto"),
            "training_backend": _training_backend_label(meta),
            "model_init": meta.get("model_init", "paper"),
            "keras_application": meta.get("keras_application"),
            "keras_weights": meta.get("keras_weights"),
            "offchain": offchain,
            "weight_storage": "off-chain (enclave data dir)" if offchain else "on-chain (ledger)",
            "register_clients": bool(meta.get("register_clients", method == "ccfl")),
            "k_sigma": meta.get("k_sigma"),
            "use_adaptive": meta.get("use_adaptive", True),
            "partitioned": bool(meta.get("partitioned", False)),
            "dp_sigma": meta.get("dp_sigma"),
            "is_ccfl": method == "ccfl",
            "is_he": method in ("he_based", "he_fedavg", "he"),
            "is_baseline": method not in ("ccfl", "ahda"),
        }
        out.append(entry)
    # CCFL experiments first, then other FL baselines
    out.sort(key=lambda c: (0 if c.get("is_ccfl") else 1, c["id"]))
    return out


def _log_reader(pipe) -> None:
    global _experiment_log
    if pipe is None:
        return
    for line in iter(pipe.readline, b""):
        text = line.decode("utf-8", errors="replace").rstrip()
        with _lock:
            _experiment_log.append(text)
            if len(_experiment_log) > 2000:
                _experiment_log = _experiment_log[-1500:]


_ROUND_LOG_RE = re.compile(r"Round (\d+): acc=([\d.]+)")
_RUN_ID_RE = re.compile(r"run_id=([\w_]+)")
_MODEL_ID_RE = re.compile(r"model_id=(\d+)")


def _parse_experiment_log(log: List[str]) -> Dict[str, Any]:
    live_rounds: List[Dict[str, Any]] = []
    run_id = None
    model_id = None
    for line in log:
        m = _ROUND_LOG_RE.search(line)
        if m:
            live_rounds.append({"round": int(m.group(1)), "accuracy": float(m.group(2))})
        rid = _RUN_ID_RE.search(line)
        if rid:
            run_id = rid.group(1)
        mid = _MODEL_ID_RE.search(line)
        if mid:
            model_id = int(mid.group(1))
    latest = live_rounds[-1] if live_rounds else None
    return {
        "live_rounds": live_rounds,
        "latest_round": latest["round"] if latest else None,
        "latest_accuracy": latest["accuracy"] if latest else None,
        "run_id": run_id,
        "model_id": model_id,
    }


def experiment_log_tail(limit: int = 200) -> List[str]:
    with _lock:
        return list(_experiment_log[-limit:])


def experiment_status() -> Dict[str, Any]:
    global _experiment_proc
    running = _experiment_proc is not None and _experiment_proc.poll() is None
    exit_code = None if running else (
        _experiment_proc.poll() if _experiment_proc else _experiment_meta.get("exit_code")
    )
    with _lock:
        log_tail = _experiment_log[-120:]
        meta = dict(_experiment_meta)
    parsed = _parse_experiment_log(log_tail)
    cfg_summary = meta.get("config_summary") or {}
    rounds_total = cfg_summary.get("rounds")
    start_round = int(meta.get("start_round") or cfg_summary.get("start_round") or 0)
    if rounds_total is not None:
        rounds_total = int(rounds_total)
        rounds_done = len(parsed["live_rounds"])
        if parsed["latest_round"] is not None:
            rounds_done = parsed["latest_round"] - start_round + 1
    else:
        rounds_done = len(parsed["live_rounds"])
    progress = {
        **parsed,
        "rounds_done": max(0, rounds_done),
        "rounds_total": rounds_total,
        "start_round": start_round,
        "config_label": cfg_summary.get("id") or meta.get("config", ""),
    }
    return {
        "running": running,
        "exit_code": exit_code,
        "meta": meta,
        "log_tail": log_tail,
        "progress": progress,
    }


def check_tensorflow() -> Dict[str, Any]:
    try:
        r = subprocess.run(
            [_python(), "-c", "import tensorflow as tf; print(tf.__version__)"],
            cwd=str(WORKSPACE_DIR),
            capture_output=True,
            text=True,
            timeout=90,
        )
        if r.returncode == 0:
            return {"ok": True, "version": (r.stdout or "").strip()}
        detail = ((r.stderr or "") + (r.stdout or "")).strip()
        hint = ""
        if "AVX" in detail or r.returncode in (-6, 134):
            hint = (
                "TensorFlow needs AVX on this CPU. Use config fl_backend: numpy "
                "(mnist_5clients_ccfl.yaml already does) or rebuild devcontainer without linux/amd64."
            )
        return {"ok": False, "detail": detail, "hint": hint}
    except Exception as exc:
        return {"ok": False, "detail": str(exc)}


def run_experiment(
    config_path: str,
    platform: str = "virtual",
    model_id: Optional[int] = None,
    start_round: Optional[int] = None,
) -> Dict[str, Any]:
    global _experiment_proc, _experiment_log, _experiment_meta

    cfg = Path(config_path)
    if not cfg.is_file():
        cfg = WORKSPACE_DIR / config_path
    if not cfg.is_file():
        return {"ok": False, "error": f"Config not found: {config_path}"}

    ccf = check_ccf()
    if not ccf.get("up"):
        return {"ok": False, "error": "CCF is not running. Start it from System tab or: make run-virtual SANDBOX_USERS=5"}

    certs = check_certs()
    if not certs.get("ok"):
        return {
            "ok": False,
            "error": "Missing user certificates. Restart CCF with SANDBOX_USERS=5",
            "certs": certs,
        }

    try:
        import yaml

        with cfg.open() as f:
            exp_cfg = yaml.safe_load(f) or {}
        need = int(exp_cfg.get("num_clients", 5))
        have = int(certs.get("user_count", 0))
        if need > have:
            return {
                "ok": False,
                "error": (
                    f"Config needs {need} clients but CCF only has {have} user certificates. "
                    f"Use mnist_5clients_ccfl.yaml, or restart CCF: "
                    f"make run-virtual SANDBOX_USERS={need}"
                ),
            }
    except Exception:
        pass

    with _lock:
        if _experiment_proc is not None and _experiment_proc.poll() is None:
            return {"ok": False, "error": "An experiment is already running"}

    env = os.environ.copy()
    env["CCF_URL"] = CCF_APP_URL
    env["CCF_WORKSPACE"] = str(WORKSPACE_DIR / "workspace" / "sandbox_common")
    # Allow NumPy backend when TensorFlow aborts (AVX); config fl_backend: numpy takes precedence
    tf_ok = check_tensorflow().get("ok")
    if not tf_ok:
        env["FL_BACKEND"] = "numpy"

    cmd = [
        _python(),
        "-m",
        "experiments.runner.run_ccf_fl",
        "--platform",
        platform,
        "--config",
        _config_arg(cfg),
    ]
    if model_id is not None:
        cmd.extend(["--model-id", str(model_id)])
    if start_round is not None:
        cmd.extend(["--start-round", str(start_round)])

    config_summary: Dict[str, Any] = {"id": cfg.name}
    try:
        with cfg.open() as f:
            loaded = yaml.safe_load(f) or {}
        config_summary.update(
            {
                "dataset": loaded.get("dataset"),
                "method": loaded.get("method"),
                "rounds": loaded.get("rounds"),
                "num_clients": loaded.get("num_clients"),
                "attack": loaded.get("attack", "none"),
            }
        )
    except Exception:
        pass

    with _lock:
        _experiment_log = []
        _experiment_meta = {
            "config": str(cfg),
            "config_summary": config_summary,
            "model_id": model_id,
            "start_round": start_round if start_round is not None else 0,
            "started_at": time.time(),
            "command": " ".join(cmd),
        }

    _experiment_proc = subprocess.Popen(
        cmd,
        cwd=str(WORKSPACE_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    threading.Thread(target=_log_reader, args=(_experiment_proc.stdout,), daemon=True).start()

    return {"ok": True, "pid": _experiment_proc.pid, "command": cmd}


def stop_experiment() -> Dict[str, Any]:
    global _experiment_proc, _experiment_meta
    if _experiment_proc is None or _experiment_proc.poll() is not None:
        return {"ok": True, "message": "No running experiment"}
    try:
        _experiment_proc.send_signal(signal.SIGINT)
        _experiment_proc.wait(timeout=15)
    except Exception:
        _experiment_proc.kill()
    _experiment_meta["exit_code"] = _experiment_proc.poll()
    _experiment_proc = None
    return {"ok": True, "exit_code": _experiment_meta.get("exit_code")}


def _read_metrics(run_dir: Path) -> List[Dict[str, Any]]:
    metrics_path = run_dir / "metrics.jsonl"
    if not metrics_path.is_file():
        return []
    rows: List[Dict[str, Any]] = []
    with metrics_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _summarize_run(run_dir: Path) -> Dict[str, Any]:
    run_id = run_dir.name
    config: Dict[str, Any] = {}
    config_path = run_dir / "config.json"
    if config_path.is_file():
        try:
            config = json.loads(config_path.read_text())
        except json.JSONDecodeError:
            pass

    metrics = _read_metrics(run_dir)
    accuracies = [float(m["accuracy"]) for m in metrics if "accuracy" in m]
    final_acc = accuracies[-1] if accuracies else None
    best_acc = max(accuracies) if accuracies else None
    total_ms = sum(float(m.get("elapsed_ms", 0)) for m in metrics)
    last_agg = metrics[-1].get("aggregation", {}) if metrics else {}

    return {
        "id": run_id,
        "path": str(run_dir),
        "dataset": config.get("dataset") or (metrics[0].get("dataset") if metrics else ""),
        "method": config.get("method") or (metrics[0].get("method") if metrics else ""),
        "num_clients": config.get("num_clients"),
        "rounds_planned": config.get("rounds"),
        "rounds_completed": len(metrics),
        "final_accuracy": round(final_acc, 4) if final_acc is not None else None,
        "best_accuracy": round(best_acc, 4) if best_acc is not None else None,
        "total_time_ms": int(total_ms),
        "platform": config.get("platform") or (metrics[0].get("platform") if metrics else ""),
        "distribution": config.get("distribution"),
        "attack": config.get("attack"),
        "status": "complete" if metrics else "no_metrics",
        "last_round": metrics[-1].get("round") if metrics else None,
        "clients_accepted": last_agg.get("num_accepted"),
        "clients_rejected": last_agg.get("num_rejected"),
        "modified_at": run_dir.stat().st_mtime,
    }


def list_results() -> List[Dict[str, Any]]:
    if not RESULTS_DIR.is_dir():
        return []
    runs = []
    for path in sorted(RESULTS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if path.is_dir():
            runs.append(_summarize_run(path))
    return runs[:30]


def compare_results(run_ids: List[str]) -> Dict[str, Any]:
    series: List[Dict[str, Any]] = []
    for rid in run_ids[:4]:
        rid = rid.strip()
        if not rid:
            continue
        detail = get_result_detail(rid)
        if not detail.get("ok"):
            continue
        series.append(
            {
                "id": rid,
                "summary": detail.get("summary", {}),
                "rounds": detail.get("rounds", []),
            }
        )
    return {"ok": bool(series), "series": series, "error": None if series else "No valid runs"}


def metrics_export_path(run_id: str) -> Optional[Path]:
    path = RESULTS_DIR / run_id / "metrics.jsonl"
    return path if path.is_file() else None


def get_result_detail(run_id: str) -> Dict[str, Any]:
    run_dir = RESULTS_DIR / run_id
    if not run_dir.is_dir():
        return {"ok": False, "error": f"Run not found: {run_id}"}
    config: Dict[str, Any] = {}
    if (run_dir / "config.json").is_file():
        try:
            config = json.loads((run_dir / "config.json").read_text())
        except json.JSONDecodeError:
            pass
    metrics = _read_metrics(run_dir)
    rounds = []
    for m in metrics:
        agg = m.get("aggregation") or {}
        rounds.append(
            {
                "round": m.get("round"),
                "accuracy": m.get("accuracy"),
                "elapsed_ms": m.get("elapsed_ms"),
                "comm_bytes": m.get("comm_bytes"),
                "num_accepted": agg.get("num_accepted"),
                "num_rejected": agg.get("num_rejected"),
                "threshold": agg.get("threshold"),
            }
        )
    return {
        "ok": True,
        "summary": _summarize_run(run_dir),
        "config": config,
        "rounds": rounds,
        "metrics_path": str(run_dir / "metrics.jsonl"),
    }
