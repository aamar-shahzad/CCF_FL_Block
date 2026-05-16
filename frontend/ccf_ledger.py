"""CCF ledger & platform API — FL app endpoints + CCF built-ins (tx, commit, OpenAPI)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import os

import httpx

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
CERT_DIR = WORKSPACE_DIR / "workspace" / "sandbox_common"


def _normalize_ccf_app_url(url: str) -> str:
    u = url.rstrip("/")
    while u.endswith("/app/app"):
        u = u[: -len("/app")]
    if not u.endswith("/app"):
        u = f"{u}/app"
    return u


CCF_APP_URL = _normalize_ccf_app_url(os.environ.get("CCF_URL", "https://127.0.0.1:8000"))

# FL application endpoints (cpp/app/app.cpp) + CCF built-in RPCs
ENDPOINT_CATALOG: List[Dict[str, Any]] = [
    {
        "path": "/model/intial_model",
        "method": "POST",
        "auth": "none",
        "group": "FL app",
        "description": "Register a new global model on the ledger; returns model_id.",
    },
    {
        "path": "/model/upload/local_model_weights",
        "method": "POST",
        "auth": "user",
        "group": "FL app",
        "description": "Client uploads local weights for a round (inline JSON or HE ciphertext).",
    },
    {
        "path": "/model/register_client",
        "method": "POST",
        "auth": "member",
        "group": "FL app",
        "description": "Register a federated client before CCFL uploads (vote-mediated enrollment).",
    },
    {
        "path": "/model/aggregate_weights_local",
        "method": "PUT",
        "auth": "member",
        "group": "FL app",
        "description": "Aggregate client updates (ahda, fedavg, krum, he) inside the enclave.",
    },
    {
        "path": "/model/download/global",
        "method": "GET",
        "auth": "user",
        "group": "FL app",
        "description": "Model metadata registered at upload (dataset, architecture, Paillier keys).",
    },
    {
        "path": "/model/download_gloabl_weights",
        "method": "GET",
        "auth": "user",
        "group": "FL app",
        "description": "Latest aggregated global weights for model_id (flat array or HE blob).",
    },
    {
        "path": "/model/aggregate_stats",
        "method": "GET",
        "auth": "user",
        "group": "FL app",
        "description": "AHDA / aggregation statistics for a completed round.",
    },
    {
        "path": "/user/add",
        "method": "POST",
        "auth": "none",
        "group": "FL app",
        "description": "Sample user message store (template endpoint).",
    },
    {
        "path": "/api",
        "method": "GET",
        "auth": "user",
        "group": "CCF built-in",
        "description": "OpenAPI schema for this CCF application (all /app routes).",
    },
    {
        "path": "/tx",
        "method": "GET",
        "auth": "user",
        "group": "CCF built-in",
        "description": "Transaction status: Unknown, Pending, Committed, or Invalid.",
    },
    {
        "path": "/commit",
        "method": "GET",
        "auth": "user",
        "group": "CCF built-in",
        "description": "Latest committed transaction ID on the service.",
    },
    {
        "path": "/receipt",
        "method": "GET",
        "auth": "user",
        "group": "CCF built-in",
        "description": "Cryptographic receipt for a committed transaction (historical query).",
    },
]


def _cert_dir() -> Path:
    return CERT_DIR


def _user_client(user_id: int = 0):
    from experiments.ccf_client import CCFClient

    return CCFClient(user_id=user_id, cert_dir=_cert_dir(), base_url=CCF_APP_URL)


def _member_client():
    from experiments.ccf_client import CCFClient

    return CCFClient(member=True, cert_dir=_cert_dir(), base_url=CCF_APP_URL)


def _tx_from_response(r: httpx.Response) -> Optional[str]:
    return r.headers.get("x-ms-ccf-transaction-id")


def _http_error(exc: httpx.HTTPStatusError) -> Dict[str, Any]:
    body = ""
    try:
        body = exc.response.text[:500]
    except Exception:
        pass
    return {
        "ok": False,
        "status_code": exc.response.status_code,
        "error": body or str(exc),
    }


def _summarize_weights(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, list):
        return {
            "format": "weights_array",
            "dim": len(raw),
            "preview": raw[:16],
            "downloadable": True,
        }
    if isinstance(raw, dict) and raw.get("he"):
        cts = raw.get("ciphertexts") or []
        return {
            "format": "he_paillier",
            "dim": raw.get("dim", len(cts)),
            "scale": raw.get("scale"),
            "ciphertext_count": len(cts),
            "downloadable": True,
        }
    return {"format": "unknown", "downloadable": False}


def list_endpoint_catalog() -> List[Dict[str, Any]]:
    return ENDPOINT_CATALOG


def discover_model_ids(max_probe: int = 32) -> List[int]:
    """Probe model_id 0..max_probe-1 via metadata endpoint."""
    if not (_cert_dir() / "user0_cert.pem").is_file():
        return []
    client = _user_client(0)
    found: List[int] = []
    for model_id in range(max_probe):
        try:
            r = client.client().get(
                f"{CCF_APP_URL}/model/download/global",
                params={"model_id": model_id},
            )
            if r.status_code == 200:
                found.append(model_id)
        except httpx.HTTPStatusError:
            continue
        except Exception:
            break
    return found


def get_model_metadata(model_id: int, user_id: int = 0) -> Dict[str, Any]:
    try:
        r = _user_client(user_id).client().get(
            f"{CCF_APP_URL}/model/download/global",
            params={"model_id": model_id},
        )
        r.raise_for_status()
        data = r.json()
        details = data.get("model_details") or {}
        return {
            "ok": True,
            "model_id": model_id,
            "dataset": details.get("dataset"),
            "architecture": details.get("architecture"),
            "num_classes": details.get("num_classes"),
            "model_init": details.get("model_init"),
            "has_paillier": "paillier_n" in details,
            "raw": data,
        }
    except httpx.HTTPStatusError as exc:
        return _http_error(exc)
    except FileNotFoundError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def get_global_weights(model_id: int, user_id: int = 0) -> Dict[str, Any]:
    try:
        raw = _user_client(user_id).get_global_weights_raw(model_id)
        summary = _summarize_weights(raw)
        return {"ok": True, "model_id": model_id, "summary": summary, "weights": raw}
    except httpx.HTTPStatusError as exc:
        return _http_error(exc)
    except FileNotFoundError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def get_aggregate_stats(model_id: int, round_no: int, user_id: int = 0) -> Dict[str, Any]:
    try:
        data = _user_client(user_id).aggregate_stats(model_id, round_no)
        return {"ok": True, "model_id": model_id, "round_no": round_no, "stats": data}
    except httpx.HTTPStatusError as exc:
        return _http_error(exc)
    except FileNotFoundError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def get_transaction_status(transaction_id: str, user_id: int = 0) -> Dict[str, Any]:
    try:
        r = _user_client(user_id).client().get(
            f"{CCF_APP_URL}/tx",
            params={"transaction_id": transaction_id},
        )
        r.raise_for_status()
        tx_hdr = r.headers.get("x-ms-ccf-transaction-id")
        return {
            "ok": True,
            "transaction_id": transaction_id,
            "status": r.json(),
            "service_tx_id": tx_hdr,
            "raw": r.json(),
        }
    except httpx.HTTPStatusError as exc:
        return _http_error(exc)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def get_commit_level(user_id: int = 0) -> Dict[str, Any]:
    try:
        r = _user_client(user_id).client().get(f"{CCF_APP_URL}/commit")
        r.raise_for_status()
        return {"ok": True, "commit": r.json(), "service_tx_id": r.headers.get("x-ms-ccf-transaction-id")}
    except httpx.HTTPStatusError as exc:
        return _http_error(exc)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def get_openapi(user_id: int = 0) -> Dict[str, Any]:
    try:
        r = _user_client(user_id).client().get(f"{CCF_APP_URL}/api")
        r.raise_for_status()
        schema = r.json()
        paths = sorted((schema.get("paths") or {}).keys()) if isinstance(schema, dict) else []
        return {"ok": True, "path_count": len(paths), "paths": paths[:80], "openapi": schema}
    except httpx.HTTPStatusError as exc:
        return _http_error(exc)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def trigger_aggregate(
    model_id: int,
    round_no: int,
    method: str = "ahda",
    k_sigma: float = 2.5,
    use_adaptive: bool = True,
    partitioned: bool = False,
) -> Dict[str, Any]:
    try:
        member = _member_client()
        params: Dict[str, Any] = {
            "model_id": model_id,
            "round_no": round_no,
            "method": method,
            "k_sigma": k_sigma,
            "use_adaptive": "true" if use_adaptive else "false",
        }
        if partitioned:
            params["partitioned"] = "true"
        r = member.client().put(
            f"{CCF_APP_URL}/model/aggregate_weights_local",
            params=params,
        )
        r.raise_for_status()
        return {
            "ok": True,
            "service_tx_id": _tx_from_response(r),
            "result": r.json(),
        }
    except httpx.HTTPStatusError as exc:
        return _http_error(exc)
    except FileNotFoundError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def weights_download_json(model_id: int, user_id: int = 0) -> Optional[bytes]:
    data = get_global_weights(model_id, user_id=user_id)
    if not data.get("ok"):
        return None
    return json.dumps(data.get("weights"), indent=2).encode("utf-8")


def add_user(msg: str) -> Dict[str, Any]:
    try:
        r = httpx.Client(verify=False, timeout=30.0).post(
            f"{CCF_APP_URL}/user/add",
            json={"msg": msg},
        )
        r.raise_for_status()
        return {
            "ok": True,
            "status_code": r.status_code,
            "service_tx_id": _tx_from_response(r),
            "raw": r.json() if r.content else {},
        }
    except httpx.HTTPStatusError as exc:
        return _http_error(exc)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def upload_initial_model(model_name: str, model_data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        r = httpx.Client(verify=False, timeout=60.0).post(
            f"{CCF_APP_URL}/model/intial_model",
            json={"global_model": {"model_name": model_name, "model_data": model_data}},
        )
        r.raise_for_status()
        body = r.json()
        return {
            "ok": True,
            "model_id": body.get("model_id"),
            "service_tx_id": _tx_from_response(r),
            "raw": body,
        }
    except httpx.HTTPStatusError as exc:
        return _http_error(exc)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def upload_local_weights(
    model_id: int,
    round_no: int,
    weights: List[float],
    client_id: str = "",
    user_id: int = 0,
) -> Dict[str, Any]:
    try:
        payload: Dict[str, Any] = {
            "model_id": model_id,
            "round_no": round_no,
            "weights_json": weights,
        }
        if client_id:
            payload["client_id"] = client_id
        r = _user_client(user_id).client().post(
            f"{CCF_APP_URL}/model/upload/local_model_weights",
            json=payload,
        )
        r.raise_for_status()
        return {"ok": True, "service_tx_id": _tx_from_response(r), "raw": r.json()}
    except httpx.HTTPStatusError as exc:
        return _http_error(exc)
    except FileNotFoundError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def register_client(client_id: str, cert_fingerprint: str = "") -> Dict[str, Any]:
    try:
        member = _member_client()
        r = member.client().post(
            f"{CCF_APP_URL}/model/register_client",
            json={
                "client_id": client_id,
                "cert_fingerprint": cert_fingerprint or client_id,
            },
        )
        r.raise_for_status()
        return {
            "ok": True,
            "service_tx_id": _tx_from_response(r),
            "raw": r.json(),
        }
    except httpx.HTTPStatusError as exc:
        return _http_error(exc)
    except FileNotFoundError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def get_receipt(transaction_id: str, user_id: int = 0) -> Dict[str, Any]:
    try:
        r = _user_client(user_id).client().get(
            f"{CCF_APP_URL}/receipt",
            params={"transaction_id": transaction_id},
        )
        if r.status_code == 202:
            return {
                "ok": True,
                "pending": True,
                "status_code": 202,
                "retry_after": r.headers.get("Retry-After"),
                "message": "Historical query pending — retry after a few seconds.",
            }
        r.raise_for_status()
        return {
            "ok": True,
            "transaction_id": transaction_id,
            "receipt": r.json(),
            "service_tx_id": r.headers.get("x-ms-ccf-transaction-id"),
        }
    except httpx.HTTPStatusError as exc:
        return _http_error(exc)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
