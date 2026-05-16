"""HTTP client for CCF FL endpoints with mTLS (virtual or SGX sandbox)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import httpx

WeightPayload = Union[List[float], Dict[str, Any]]


def normalize_ccf_app_url(url: str) -> str:
    """Ensure exactly one /app suffix (CCF user endpoints live under /app/...)."""
    u = url.rstrip("/")
    while u.endswith("/app/app"):
        u = u[: -len("/app")]
    if not u.endswith("/app"):
        u = f"{u}/app"
    return u


def get_ccf_app_url() -> str:
    return normalize_ccf_app_url(os.environ.get("CCF_URL", "https://127.0.0.1:8000"))


def count_user_certs(cert_dir: Optional[Path] = None) -> int:
    """Number of userN_cert.pem files present (CCF sandbox --initial-user-count N)."""
    cert_dir = Path(cert_dir or discover_sandbox()["cert_dir"])
    n = 0
    for i in range(256):
        if (cert_dir / f"user{i}_cert.pem").is_file() and (
            cert_dir / f"user{i}_privk.pem"
        ).is_file():
            n = i + 1
        elif i > 0:
            break
    return n


def discover_sandbox(platform: str = "auto") -> dict[str, Any]:
    """Locate CCF sandbox certificates and detect platform."""
    candidates = [
        Path("workspace/sandbox_common"),
        Path(".sandbox_ccf"),
        Path("workspace"),
    ]
    cert_dir = Path(os.environ.get("CCF_WORKSPACE", ".sandbox_ccf"))
    for c in candidates:
        if (c / "member0_cert.pem").exists():
            cert_dir = c
            break
        default_member = c / "default_member_0"
        if default_member.exists():
            for sub in default_member.iterdir():
                if sub.is_dir() and (sub / "member0_cert.pem").exists():
                    cert_dir = sub
                    break

    plat = platform
    if plat == "auto":
        if Path("build/liblskv.enclave.so.signed").exists():
            plat = "sgx"
        else:
            plat = "virtual"

    url = get_ccf_app_url()
    return {"platform": plat, "cert_dir": cert_dir, "url": url}


class CCFClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        cert_dir: Optional[Path] = None,
        user_id: int = 0,
        member: bool = False,
    ):
        self.base_url = normalize_ccf_app_url(base_url or get_ccf_app_url())
        self.cert_dir = Path(cert_dir or discover_sandbox()["cert_dir"])
        self.user_id = user_id
        self.member = member
        self._client: Optional[httpx.Client] = None

    def _certs(self) -> tuple[str, str]:
        if self.member:
            cert = self.cert_dir / "member0_cert.pem"
            key = self.cert_dir / "member0_privk.pem"
        else:
            cert = self.cert_dir / f"user{self.user_id}_cert.pem"
            key = self.cert_dir / f"user{self.user_id}_privk.pem"
        if not cert.is_file() or not key.is_file():
            available = count_user_certs(self.cert_dir)
            raise FileNotFoundError(
                f"Missing {cert.name} (sandbox has {available} users). "
                f"Restart CCF with SANDBOX_USERS>={self.user_id + 1} or use a config with "
                f"num_clients<={available}."
            )
        return str(cert), str(key)

    def client(self) -> httpx.Client:
        if self._client is None:
            cert, key = self._certs()
            self._client = httpx.Client(
                cert=(cert, key),
                verify=False,
                timeout=300.0,
                http2=True,
            )
        return self._client

    def upload_model(self, model_name: str, model_data: dict) -> int:
        r = self.client().post(
            f"{self.base_url}/model/intial_model",
            json={"global_model": {"model_name": model_name, "model_data": model_data}},
        )
        r.raise_for_status()
        return r.json()["model_id"]

    def upload_weights(
        self,
        model_id: int,
        round_no: int,
        weights: WeightPayload,
        client_id: str = "",
        offchain: bool = True,
    ) -> dict:
        payload: dict[str, Any] = {
            "model_id": model_id,
            "round_no": round_no,
            "client_id": client_id,
        }
        if isinstance(weights, dict):
            payload["weights_json"] = weights
        else:
            # Non-empty weights_json required (empty [] + weight_ref alone returns 400).
            # Enclave persists to data/offchain and records weight_ref on the ledger.
            payload["weights_json"] = list(weights)

        r = self.client().post(
            f"{self.base_url}/model/upload/local_model_weights",
            json=payload,
        )
        r.raise_for_status()
        return r.json()

    def aggregate(
        self,
        model_id: int,
        round_no: int,
        method: str = "ahda",
        k_sigma: float = 2.5,
        partitioned: bool = False,
        use_adaptive: bool = True,
    ) -> dict:
        params: dict[str, Any] = {
            "model_id": model_id,
            "round_no": round_no,
            "method": method,
            "k_sigma": k_sigma,
            "use_adaptive": "true" if use_adaptive else "false",
        }
        if partitioned:
            params["partitioned"] = "true"
        r = self.client().put(
            f"{self.base_url}/model/aggregate_weights_local",
            params=params,
        )
        r.raise_for_status()
        return r.json()

    def _user_reader(self) -> CCFClient:
        return CCFClient(user_id=0, cert_dir=self.cert_dir, base_url=self.base_url)

    def get_global_weights_raw(self, model_id: int) -> Any:
        # /model/download_gloabl_weights requires user cert, not member.
        client = self._user_reader() if self.member else self
        r = client.client().get(
            f"{self.base_url}/model/download_gloabl_weights",
            params={"model_id": model_id},
        )
        r.raise_for_status()
        return r.json()["global_model"]

    def get_global_weights(self, model_id: int) -> list[float]:
        raw = self.get_global_weights_raw(model_id)
        if isinstance(raw, list):
            return raw
        raise ValueError("Global model is HE-encrypted; use get_global_weights_raw + decrypt")

    def estimate_round_comm_bytes(
        self, model_id: int, round_no: int, offchain: bool = True
    ) -> int:
        """Rough on-ledger bytes for this round (metadata + optional inline weights)."""
        if offchain:
            return 120 * 20
        return 1750 * 20

    def register_client(self, client_id: str, cert_fingerprint: str = "") -> dict:
        member = CCFClient(member=True, cert_dir=self.cert_dir, base_url=self.base_url)
        r = member.client().post(
            f"{self.base_url}/model/register_client",
            json={
                "client_id": client_id,
                "cert_fingerprint": cert_fingerprint or client_id,
            },
        )
        r.raise_for_status()
        return r.json()

    def aggregate_stats(self, model_id: int, round_no: int) -> dict:
        r = self.client().get(
            f"{self.base_url}/model/aggregate_stats",
            params={"model_id": model_id, "round_no": round_no},
        )
        r.raise_for_status()
        return r.json()
