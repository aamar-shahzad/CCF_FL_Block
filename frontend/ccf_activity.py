"""CCF ledger activity feed: recent commits, transaction scan, UI/experiment events."""

from __future__ import annotations

import re
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Deque, Dict, List, Optional, Tuple

from ccf_ledger import get_commit_level, get_transaction_status

_ACTIVITY: Deque[Dict[str, Any]] = deque(maxlen=200)
_last_seen_commit: Optional[str] = None
_seen_experiment_lines: set[str] = set()

_CCFL_LINE = re.compile(
    r"\[CCFL\]|Registered new model|upload|aggregate|Loaded global|Round \d+",
    re.I,
)


def record_activity(
    source: str,
    action: str,
    *,
    tx_id: Optional[str] = None,
    status: Optional[str] = None,
    detail: Optional[str] = None,
    ok: bool = True,
    method: Optional[str] = None,
    path: Optional[str] = None,
) -> None:
    _ACTIVITY.appendleft(
        {
            "ts": time.time(),
            "source": source,
            "action": action,
            "tx_id": tx_id,
            "status": status,
            "detail": detail,
            "ok": ok,
            "method": method,
            "path": path,
        }
    )


def parse_tx_id(tx_id: str) -> Optional[Tuple[int, int]]:
    if not tx_id or "." not in tx_id:
        return None
    try:
        view_s, seq_s = tx_id.split(".", 1)
        return int(view_s), int(seq_s)
    except ValueError:
        return None


def scan_recent_transactions(
    limit: int = 24,
    user_id: int = 0,
) -> List[Dict[str, Any]]:
    commit = get_commit_level(user_id=user_id)
    if not commit.get("ok"):
        return []
    commit_body = commit.get("commit") or {}
    latest_id = commit_body.get("transaction_id") or ""
    parsed = parse_tx_id(latest_id)
    if not parsed:
        return []
    view, seq = parsed
    start = max(1, seq - limit + 1)

    def fetch_one(sequence: int) -> Dict[str, Any]:
        tid = f"{view}.{sequence}"
        result = get_transaction_status(tid, user_id=user_id)
        status_body = result.get("status") if isinstance(result.get("status"), dict) else {}
        st = status_body.get("status") if status_body else None
        if not st and result.get("raw"):
            st = result["raw"].get("status")
        return {
            "transaction_id": tid,
            "status": st or ("Error" if not result.get("ok") else "Unknown"),
            "ok": result.get("ok", False),
            "service_tx_id": result.get("service_tx_id"),
        }

    rows: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(fetch_one, s): s for s in range(start, seq + 1)}
        for fut in as_completed(futures):
            rows.append(fut.result())
    rows.sort(key=lambda r: parse_tx_id(r["transaction_id"]) or (0, 0), reverse=True)
    return rows


def get_experiment_ccf_lines(lines: List[str], limit: int = 40) -> List[str]:
    matched = [ln for ln in lines if _CCFL_LINE.search(ln)]
    return matched[-limit:]


def get_activity_feed(
    user_id: int = 0,
    tx_limit: int = 24,
    experiment_log: Optional[List[str]] = None,
) -> Dict[str, Any]:
    global _last_seen_commit

    commit = get_commit_level(user_id=user_id)
    transactions: List[Dict[str, Any]] = []
    if commit.get("ok"):
        transactions = scan_recent_transactions(limit=tx_limit, user_id=user_id)
        latest = (commit.get("commit") or {}).get("transaction_id")
        if latest and latest != _last_seen_commit:
            if _last_seen_commit is not None:
                record_activity(
                    "ledger",
                    "commit_advanced",
                    tx_id=latest,
                    status="Committed",
                    detail=f"Ledger advanced ({_last_seen_commit} → {latest})",
                    ok=True,
                )
            _last_seen_commit = latest

    exp_lines: List[str] = []
    if experiment_log:
        exp_lines = get_experiment_ccf_lines(experiment_log)
        for line in exp_lines:
            key = line.strip()
            if key and key not in _seen_experiment_lines:
                _seen_experiment_lines.add(key)
                if len(_seen_experiment_lines) > 500:
                    _seen_experiment_lines.clear()
                record_activity("experiment", "log", detail=key, ok=True)

    events = list(_ACTIVITY)[:80]
    committed = sum(1 for t in transactions if t.get("status") == "Committed")
    pending = sum(1 for t in transactions if t.get("status") == "Pending")

    return {
        "ok": commit.get("ok", False),
        "commit": commit.get("commit"),
        "commit_error": commit.get("error") if not commit.get("ok") else None,
        "transactions": transactions,
        "events": events,
        "experiment_lines": exp_lines,
        "stats": {
            "tx_scanned": len(transactions),
            "committed": committed,
            "pending": pending,
            "event_count": len(events),
        },
        "polled_at": time.time(),
    }
