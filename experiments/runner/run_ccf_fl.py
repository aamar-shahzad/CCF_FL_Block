#!/usr/bin/env python3
"""
Real CCFL federated learning against a live CCF network (virtual or SGX).

All defenses and baselines execute on CCF — no simulated latency or fake metrics.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from pathlib import Path

import httpx
import numpy as np
import yaml

from experiments.attacks.inject import apply_attack
from experiments.baselines.he_paillier import PaillierContext
from experiments.ccf_client import CCFClient, count_user_certs, discover_sandbox
from experiments.clients.fl_backend import get_client_module, resolve_backend
from experiments.datasets.registry import load_dataset
from experiments.defenses.dp_fedavg import add_gaussian_noise
from experiments.defenses.methods import resolve_ccf_method, use_offchain
from experiments.metrics.logger import MetricsLogger

def load_config(path: Path) -> dict:
    with path.open() as f:
        return yaml.safe_load(f)


def _load_global_weights_into_model(
    member: CCFClient,
    model_id: int,
    global_model: object,
    set_weights,
    he_ctx: PaillierContext | None,
) -> bool:
    """Return True if weights were loaded from CCF."""
    try:
        raw_global = member.get_global_weights_raw(model_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return False
        raise
    if he_ctx and isinstance(raw_global, dict) and raw_global.get("he"):
        weights = he_ctx.decrypt_weights(raw_global)
    else:
        weights = raw_global if isinstance(raw_global, list) else list(raw_global)
    set_weights(global_model, weights)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="CCFL on real CCF (virtual/SGX)")
    parser.add_argument("--config", type=Path, default=Path("experiments/config/mnist_iid.yaml"))
    parser.add_argument("--platform", choices=["virtual", "sgx", "auto"], default="auto")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--ccf-url", default="")
    parser.add_argument(
        "--model-id",
        type=int,
        default=None,
        help="Reuse an existing CCF model (skip /model/intial_model upload)",
    )
    parser.add_argument(
        "--start-round",
        type=int,
        default=None,
        help="First FL round index (default 0, or config start_round)",
    )
    args = parser.parse_args()

    sandbox = discover_sandbox(args.platform)
    if args.ccf_url:
        os.environ["CCF_URL"] = args.ccf_url
    os.environ["CCF_WORKSPACE"] = str(sandbox["cert_dir"])

    cfg = load_config(args.config)
    os.environ["FL_BACKEND"] = resolve_backend(cfg)
    fl = get_client_module(cfg)
    build_model = fl.build_model
    train_local = fl.train_local
    flatten_weights = fl.flatten_weights
    set_weights = fl.set_weights
    evaluate = fl.evaluate

    run_id = args.run_id or f"{cfg['dataset']}_{cfg['method']}_{uuid.uuid4().hex[:8]}"
    logger = MetricsLogger(run_id)

    np.random.seed(cfg.get("seed", 42))
    dataset_name = cfg["dataset"]
    cert_dir = Path(sandbox["cert_dir"])
    available_users = count_user_certs(cert_dir)
    if available_users == 0:
        raise RuntimeError(f"No user certificates in {cert_dir}. Start CCF with SANDBOX_USERS>=5.")

    num_clients = int(cfg.get("num_clients", 4))
    num_users = min(int(cfg.get("sandbox_users", available_users)), available_users)
    if num_clients > available_users:
        print(
            f"[CCFL] Note: {num_clients} FL clients, {available_users} CCF user certs "
            f"(user ids wrap with modulo {available_users})"
        )
    rounds = int(cfg.get("rounds", 5))
    start_round = int(
        args.start_round if args.start_round is not None else cfg.get("start_round", 0)
    )
    if start_round < 0:
        start_round = 0
    malicious_frac = float(cfg.get("malicious_frac", 0.0))
    method = cfg.get("method", "ccfl")
    attack = cfg.get("attack", "none")
    distribution = cfg.get("distribution", "iid")
    epochs = int(cfg.get("local_epochs", 2))
    register_clients = cfg.get("register_clients", method == "ccfl")
    offchain = use_offchain(method, cfg.get("offchain", True))
    dp_sigma = float(cfg.get("dp_sigma", 0.01))
    ccf_method = resolve_ccf_method(method)

    he_ctx: PaillierContext | None = None
    if method in ("he_based", "he_fedavg", "he"):
        he_ctx = PaillierContext.generate(
            key_length=int(cfg.get("he_key_bits", 1024)),
            scale=int(cfg.get("he_scale", 10_000)),
        )

    data = load_dataset(dataset_name, num_clients, distribution, cfg.get("alpha", 0.5))
    shards, x_test, y_test = data["shards"], data["x_test"], data["y_test"]
    num_classes = int(np.max(y_test)) + 1

    global_model = build_model(dataset_name, (), num_classes, cfg=cfg)
    model_meta = {
        "dataset": dataset_name,
        "num_classes": num_classes,
        "architecture": global_model.name,
        "model_init": cfg.get("model_init", "paper"),
    }
    if he_ctx:
        model_meta["paillier"] = he_ctx.public_dict()
        model_meta["paillier_n"] = str(he_ctx.public_key.n)
        model_meta["paillier_g"] = str(he_ctx.public_key.g)

    member = CCFClient(member=True, cert_dir=sandbox["cert_dir"])
    reuse_id = args.model_id if args.model_id is not None else cfg.get("model_id")
    if reuse_id is not None and str(reuse_id).strip() != "":
        model_id = int(reuse_id)
        print(f"[CCFL] Reusing existing model_id={model_id} (skipping model upload)")
        if _load_global_weights_into_model(
            member, model_id, global_model, set_weights, he_ctx
        ):
            print("[CCFL] Loaded global weights from CCF")
        else:
            print("[CCFL] No global weights on ledger yet; starting from local model init")
    else:
        model_id = member.upload_model(cfg.get("model_name", dataset_name), model_meta)
        print(f"[CCFL] Registered new model_id={model_id}")

    malicious_ids = set(
        np.random.choice(
            num_clients,
            size=int(num_clients * malicious_frac),
            replace=False,
        ).tolist()
    )

    print(
        f"CCFL run_id={run_id} platform={sandbox['platform']} "
        f"ccf={sandbox['url']} clients={num_clients} method={method} -> ccf:{ccf_method} "
        f"model_id={model_id} rounds={start_round}..{start_round + rounds - 1}"
    )

    for round_no in range(start_round, start_round + rounds):
        t0 = time.perf_counter()
        for cid in range(num_clients):
            x_local, y_local = shards[cid]
            if len(x_local) == 0:
                continue

            local = build_model(dataset_name, (), num_classes, cfg=cfg)
            set_weights(local, flatten_weights(global_model))

            y_train = y_local
            if cid in malicious_ids and attack == "label_flip":
                _, y_train = apply_attack(attack, [], y_local, num_classes)

            train_local(
                local, x_local, y_train,
                epochs=epochs, dataset=dataset_name, num_classes=num_classes,
            )
            weights = flatten_weights(local)

            if cid in malicious_ids and attack != "label_flip":
                weights, _ = apply_attack(
                    attack, weights,
                    attack_strength=float(cfg.get("attack_strength", 0.5)),
                )
            if method == "dp_fedavg":
                weights = add_gaussian_noise(weights, sigma=dp_sigma)

            user_idx = cid % available_users
            user = CCFClient(user_id=user_idx, cert_dir=sandbox["cert_dir"])
            client_id = f"client_{cid}"

            def do_upload(c_id: str, w: list[float], u: CCFClient) -> None:
                if register_clients and round_no == start_round:
                    try:
                        member.register_client(c_id, cert_fingerprint=c_id)
                    except Exception:
                        pass
                if he_ctx is not None:
                    payload = he_ctx.encrypt_weights(w)
                    u.upload_weights(
                        model_id, round_no, payload,
                        client_id=c_id if register_clients else "",
                        offchain=False,
                    )
                else:
                    u.upload_weights(
                        model_id, round_no, w,
                        client_id=c_id if register_clients else "",
                        offchain=offchain,
                    )

            if attack == "sybil" and cid in malicious_ids:
                for s in range(int(cfg.get("sybil_count", 3))):
                    sid = f"{client_id}_sybil_{s}"
                    do_upload(sid, weights, CCFClient(user_id=user_idx, cert_dir=sandbox["cert_dir"]))
            else:
                do_upload(client_id, weights, user)

        agg = member.aggregate(
            model_id, round_no,
            method=ccf_method,
            k_sigma=float(cfg.get("k_sigma", 2.5)),
            partitioned=bool(cfg.get("partitioned", False)),
            use_adaptive=bool(cfg.get("use_adaptive", True)),
        )

        raw_global = member.get_global_weights_raw(model_id)
        if he_ctx and isinstance(raw_global, dict) and raw_global.get("he"):
            weights = he_ctx.decrypt_weights(raw_global)
        else:
            weights = raw_global if isinstance(raw_global, list) else list(raw_global)
        set_weights(global_model, weights)

        acc = evaluate(global_model, x_test, y_test, dataset=dataset_name, num_classes=num_classes)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        comm_bytes = member.estimate_round_comm_bytes(model_id, round_no, offchain=offchain)

        logger.log({
            "round": round_no,
            "accuracy": acc,
            "method": method,
            "ccf_method": ccf_method,
            "platform": sandbox["platform"],
            "dataset": dataset_name,
            "malicious_frac": malicious_frac,
            "attack": attack,
            "distribution": distribution,
            "elapsed_ms": elapsed_ms,
            "comm_bytes": comm_bytes,
            "aggregation": agg.get("aggregation", {}),
        })
        print(f"Round {round_no}: acc={acc:.4f} ms={elapsed_ms:.0f} comm={comm_bytes}B")

    meta = {**cfg, "platform": sandbox["platform"], "ccf_url": sandbox["url"]}
    (logger.run_dir / "config.json").write_text(json.dumps(meta, indent=2))
    print(f"Done. Metrics: {logger.path}")


if __name__ == "__main__":
    main()
