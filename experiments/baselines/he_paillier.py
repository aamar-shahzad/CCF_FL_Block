"""
Real Paillier additive homomorphic encryption for the HE-FedAvg baseline.
Clients encrypt quantized weight updates; CCF aggregates ciphertexts homomorphically.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

try:
    from phe import paillier
except ImportError:
    paillier = None  # type: ignore

DEFAULT_SCALE = 10_000


@dataclass
class PaillierContext:
    public_key: Any
    private_key: Any
    scale: int = DEFAULT_SCALE

    def public_dict(self) -> dict:
        return {
            "n": str(self.public_key.n),
            "g": str(self.public_key.g),
            "scale": self.scale,
        }

    @classmethod
    def generate(cls, key_length: int = 1024, scale: int = DEFAULT_SCALE) -> "PaillierContext":
        if paillier is None:
            raise ImportError("Install 'phe' package: pip install phe")
        pub, priv = paillier.generate_paillier_keypair(n_length=key_length)
        return cls(public_key=pub, private_key=priv, scale=scale)

    @classmethod
    def from_public_dict(cls, d: dict) -> "PaillierContext":
        if paillier is None:
            raise ImportError("pip install phe")
        n = int(d["n"])
        g = int(d["g"])
        pub = paillier.PaillierPublicKey(n)
        pub.g = g
        return cls(public_key=pub, private_key=None, scale=int(d.get("scale", DEFAULT_SCALE)))

    def encrypt_weights(self, weights: list[float]) -> dict:
        quantized = [int(round(w * self.scale)) for w in weights]
        ciphertexts = []
        for m in quantized:
            enc = self.public_key.encrypt(m)
            ciphertexts.append(str(enc.ciphertext()))
        return {"he": True, "ciphertexts": ciphertexts, "scale": self.scale, "dim": len(weights)}

    def decrypt_weights(self, payload: dict) -> list[float]:
        if self.private_key is None:
            raise ValueError("Private key required for decryption")
        if paillier is None:
            raise ImportError("pip install phe")
        scale = int(payload.get("scale", self.scale))
        out = []
        for c_str in payload["ciphertexts"]:
            enc = paillier.EncryptedNumber(self.public_key, int(c_str))
            m = self.private_key.decrypt(enc)
            out.append(float(m) / scale)
        return out


def ciphertexts_from_upload(weights_json: Any) -> list[str] | None:
    if isinstance(weights_json, dict) and weights_json.get("he"):
        return weights_json["ciphertexts"]
    return None
