#!/usr/bin/env python3
"""
CCF Federated Learning — API proxy, control plane, and static UI (single port 5000).
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = FRONTEND_DIR.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

import requests
from flask import Flask, jsonify, request, send_file, send_from_directory
from flask_cors import CORS

from ccf_activity import get_activity_feed, record_activity
from control_api import (
    check_ccf,
    check_certs,
    check_tensorflow,
    clean_sandbox,
    compare_results,
    experiment_log_tail,
    experiment_status,
    get_result_detail,
    list_configs,
    list_results,
    metrics_export_path,
    run_experiment,
    stop_experiment,
)
from ccf_ledger import (
    add_user,
    discover_model_ids,
    get_aggregate_stats,
    get_commit_level,
    get_global_weights,
    get_model_metadata,
    get_openapi,
    get_receipt,
    get_transaction_status,
    list_endpoint_catalog,
    register_client,
    trigger_aggregate,
    upload_initial_model,
    upload_local_weights,
    weights_download_json,
)

CCF_SERVER = os.environ.get("CCF_URL", "https://127.0.0.1:8000")
DEFAULT_SERVICE_CERT = WORKSPACE_DIR / "workspace" / "sandbox_common" / "service_cert.pem"

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
CORS(app, resources={r"/*": {"origins": "*"}})


@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/api/proxy", methods=["POST"])
def proxy_request():
    try:
        data = request.form.get("data")
        method = request.form.get("method", "GET")
        url = request.form.get("url")

        user_cert_file = request.files.get("user_cert")
        user_key_file = request.files.get("user_key")
        member_cert_file = request.files.get("member_cert")
        member_key_file = request.files.get("member_key")
        service_cert_path = request.form.get("service_cert_path", str(DEFAULT_SERVICE_CERT))
        if not os.path.isabs(service_cert_path):
            service_cert_path = os.path.normpath(
                os.path.join(WORKSPACE_DIR, service_cert_path.lstrip("./"))
            )
        if not os.path.exists(service_cert_path):
            service_cert_path = str(DEFAULT_SERVICE_CERT)

        headers = {"Content-Type": "application/json"}
        cert = None
        verify = service_cert_path if os.path.exists(service_cert_path) else False

        if user_cert_file and user_key_file:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pem") as cert_file:
                cert_file.write(user_cert_file.read())
                cert_path = cert_file.name
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pem") as key_file:
                key_file.write(user_key_file.read())
                key_path = key_file.name
            cert = (cert_path, key_path)
        elif member_cert_file and member_key_file:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pem") as cert_file:
                cert_file.write(member_cert_file.read())
                cert_path = cert_file.name
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pem") as key_file:
                key_file.write(member_key_file.read())
                key_path = key_file.name
            cert = (cert_path, key_path)

        json_data = json.loads(data) if data else None

        if method.upper() == "GET":
            response = requests.get(url, verify=verify, cert=cert, headers=headers, timeout=300)
        elif method.upper() == "POST":
            response = requests.post(
                url, verify=verify, cert=cert, headers=headers, json=json_data, timeout=300
            )
        elif method.upper() == "PUT":
            response = requests.put(
                url, verify=verify, cert=cert, headers=headers, json=json_data, timeout=300
            )
        else:
            return jsonify({"error": f"Unsupported method: {method}"}), 400

        if cert:
            try:
                os.unlink(cert[0])
                os.unlink(cert[1])
            except OSError:
                pass

        return response.text, response.status_code, {"Content-Type": "application/json"}
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "message": "CCF Proxy Server is running",
        "ledger_api": True,
        "api_version": 2,
    })


@app.errorhandler(404)
def handle_404(err):
    if request.path.startswith("/api/"):
        return jsonify(
            {
                "ok": False,
                "error": "not_found",
                "path": request.path,
                "hint": (
                    "Restart the UI server so new API routes load: "
                    "cd frontend && PROXY_PORT=8080 ../.venv/bin/python3 proxy_server.py"
                ),
            }
        ), 404
    return err


@app.errorhandler(500)
def handle_500(err):
    if request.path.startswith("/api/"):
        return jsonify(
            {
                "ok": False,
                "error": "server_error",
                "path": request.path,
                "detail": str(getattr(err, "description", err)),
            }
        ), 500
    return err


@app.route("/api/status", methods=["GET"])
def api_status():
    return jsonify(
        {
            "proxy": True,
            "ccf": check_ccf(),
            "certs": check_certs(),
            "tensorflow": check_tensorflow(),
        }
    )


@app.route("/api/tensorflow/check", methods=["GET"])
def api_tensorflow_check():
    return jsonify(check_tensorflow())


@app.route("/api/sandbox/clean", methods=["POST"])
def api_sandbox_clean():
    return jsonify(clean_sandbox())


@app.route("/api/configs", methods=["GET"])
def api_configs():
    return jsonify({"configs": list_configs()})


@app.route("/api/experiment/run", methods=["POST"])
def api_experiment_run():
    body = request.get_json(silent=True) or {}
    config = body.get("config", "experiments/config/mnist_5clients_ccfl.yaml")
    platform = body.get("platform", "virtual")
    model_id = body.get("model_id")
    start_round = body.get("start_round")
    if model_id is not None and model_id != "":
        model_id = int(model_id)
    else:
        model_id = None
    if start_round is not None and start_round != "":
        start_round = int(start_round)
    else:
        start_round = None
    return jsonify(
        run_experiment(
            config,
            platform=platform,
            model_id=model_id,
            start_round=start_round,
        )
    )


@app.route("/api/experiment/stop", methods=["POST"])
def api_experiment_stop():
    return jsonify(stop_experiment())


@app.route("/api/experiment/status", methods=["GET"])
def api_experiment_status():
    return jsonify(experiment_status())


@app.route("/api/results", methods=["GET"])
def api_results():
    return jsonify({"runs": list_results()})


@app.route("/api/results/<run_id>", methods=["GET"])
def api_result_detail(run_id: str):
    return jsonify(get_result_detail(run_id))


@app.route("/api/results/compare", methods=["GET"])
def api_results_compare():
    ids = request.args.get("ids", "")
    run_ids = [x.strip() for x in ids.split(",") if x.strip()]
    return jsonify(compare_results(run_ids))


@app.route("/api/results/<run_id>/export", methods=["GET"])
def api_result_export(run_id: str):
    path = metrics_export_path(run_id)
    if path is None:
        return jsonify({"ok": False, "error": f"No metrics for {run_id}"}), 404
    return send_file(path, as_attachment=True, download_name=f"{run_id}_metrics.jsonl")


def _ledger_action_label(path: str, method: str) -> str:
    labels = {
        ("/api/ledger/user/add", "POST"): "User message",
        ("/api/ledger/model/register", "POST"): "Register model",
        ("/api/ledger/weights/upload", "POST"): "Upload weights",
        ("/api/ledger/client/register", "POST"): "Register client",
        ("/api/ledger/aggregate", "POST"): "Aggregate round",
    }
    return labels.get((path, method), f"{method} {path}")


def _jsonify_ledger_write(data: dict, *, action: str, method: str, path: str):
    record_activity(
        "ui",
        action,
        tx_id=data.get("service_tx_id"),
        status="Committed" if data.get("ok") else None,
        detail=data.get("error") or data.get("detail"),
        ok=bool(data.get("ok")),
        method=method,
        path=path,
    )
    return jsonify(data)


@app.route("/api/ledger/activity", methods=["GET"])
def api_ledger_activity():
    user_id = int(request.args.get("user_id", 0))
    tx_limit = min(int(request.args.get("limit", 24)), 48)
    return jsonify(
        get_activity_feed(
            user_id=user_id,
            tx_limit=tx_limit,
            experiment_log=experiment_log_tail(),
        )
    )


@app.route("/api/ledger/endpoints", methods=["GET"])
def api_ledger_endpoints():
    return jsonify({"endpoints": list_endpoint_catalog()})


@app.route("/api/ledger/models", methods=["GET"])
def api_ledger_models():
    return jsonify({"model_ids": discover_model_ids()})


@app.route("/api/ledger/models/<int:model_id>/metadata", methods=["GET"])
def api_ledger_model_metadata(model_id: int):
    user_id = int(request.args.get("user_id", 0))
    return jsonify(get_model_metadata(model_id, user_id=user_id))


@app.route("/api/ledger/models/<int:model_id>/weights", methods=["GET"])
def api_ledger_model_weights(model_id: int):
    user_id = int(request.args.get("user_id", 0))
    full = request.args.get("full", "0") == "1"
    data = get_global_weights(model_id, user_id=user_id)
    if data.get("ok") and not full and "weights" in data:
        data = {**data, "weights": None}
    return jsonify(data)


@app.route("/api/ledger/models/<int:model_id>/weights/download", methods=["GET"])
def api_ledger_weights_download(model_id: int):
    user_id = int(request.args.get("user_id", 0))
    payload = weights_download_json(model_id, user_id=user_id)
    if payload is None:
        return jsonify({"ok": False, "error": "Weights not found"}), 404
    return send_file(
        io.BytesIO(payload),
        as_attachment=True,
        download_name=f"model_{model_id}_global_weights.json",
        mimetype="application/json",
    )


@app.route("/api/ledger/models/<int:model_id>/stats", methods=["GET"])
def api_ledger_model_stats(model_id: int):
    round_no = int(request.args.get("round_no", 0))
    user_id = int(request.args.get("user_id", 0))
    return jsonify(get_aggregate_stats(model_id, round_no, user_id=user_id))


@app.route("/api/ledger/tx", methods=["GET"])
def api_ledger_tx():
    tx_id = request.args.get("transaction_id", "")
    if not tx_id:
        return jsonify({"ok": False, "error": "transaction_id required"}), 400
    user_id = int(request.args.get("user_id", 0))
    return jsonify(get_transaction_status(tx_id, user_id=user_id))


@app.route("/api/ledger/commit", methods=["GET"])
def api_ledger_commit():
    user_id = int(request.args.get("user_id", 0))
    return jsonify(get_commit_level(user_id=user_id))


@app.route("/api/ledger/openapi", methods=["GET"])
def api_ledger_openapi():
    full = request.args.get("full", "0") == "1"
    user_id = int(request.args.get("user_id", 0))
    data = get_openapi(user_id=user_id)
    if data.get("ok") and not full:
        data.pop("openapi", None)
    return jsonify(data)


@app.route("/api/ledger/aggregate", methods=["POST"])
def api_ledger_aggregate():
    body = request.get_json(silent=True) or {}
    model_id = int(body.get("model_id", 0))
    round_no = int(body.get("round_no", 0))
    method = str(body.get("method", "ahda"))
    result = trigger_aggregate(
        model_id,
        round_no,
        method=method,
        k_sigma=float(body.get("k_sigma", 2.5)),
        use_adaptive=bool(body.get("use_adaptive", True)),
        partitioned=bool(body.get("partitioned", False)),
    )
    detail = f"model={model_id} round={round_no} method={method}" if result.get("ok") else None
    return _jsonify_ledger_write(
        {**result, "detail": detail},
        action="Aggregate",
        method="PUT",
        path="/model/aggregate_weights_local",
    )


@app.route("/api/ledger/user/add", methods=["POST"])
def api_ledger_user_add():
    body = request.get_json(silent=True) or {}
    msg = str(body.get("msg", "")).strip()
    if not msg:
        return jsonify({"ok": False, "error": "msg is required"}), 400
    return _jsonify_ledger_write(
        add_user(msg), action="User message", method="POST", path="/user/add"
    )


@app.route("/api/ledger/model/register", methods=["POST"])
def api_ledger_model_register():
    body = request.get_json(silent=True) or {}
    name = str(body.get("model_name", "mnist")).strip()
    data = body.get("model_data")
    if not isinstance(data, dict):
        return jsonify({"ok": False, "error": "model_data must be a JSON object"}), 400
    return _jsonify_ledger_write(
        upload_initial_model(name, data),
        action="Register model",
        method="POST",
        path="/model/intial_model",
    )


@app.route("/api/ledger/weights/upload", methods=["POST"])
def api_ledger_weights_upload():
    body = request.get_json(silent=True) or {}
    weights = body.get("weights_json") or body.get("weights")
    if not isinstance(weights, list) or not weights:
        return jsonify({"ok": False, "error": "weights_json array required"}), 400
    return _jsonify_ledger_write(
        upload_local_weights(
            int(body.get("model_id", 0)),
            int(body.get("round_no", 0)),
            [float(x) for x in weights],
            client_id=str(body.get("client_id", "")),
            user_id=int(body.get("user_id", 0)),
        ),
        action="Upload weights",
        method="POST",
        path="/model/upload/local_model_weights",
    )


@app.route("/api/ledger/client/register", methods=["POST"])
def api_ledger_client_register():
    body = request.get_json(silent=True) or {}
    cid = str(body.get("client_id", "")).strip()
    if not cid:
        return jsonify({"ok": False, "error": "client_id required"}), 400
    return _jsonify_ledger_write(
        register_client(cid, str(body.get("cert_fingerprint", cid))),
        action="Register client",
        method="POST",
        path="/model/register_client",
    )


@app.route("/api/ledger/receipt", methods=["GET"])
def api_ledger_receipt():
    tx_id = request.args.get("transaction_id", "")
    if not tx_id:
        return jsonify({"ok": False, "error": "transaction_id required"}), 400
    user_id = int(request.args.get("user_id", 0))
    return jsonify(get_receipt(tx_id, user_id=user_id))


@app.route("/<path:path>")
def static_files(path):
    """Static assets — registered last so /api/* routes take precedence."""
    if path.startswith("api/"):
        return jsonify({"error": "not found"}), 404
    target = FRONTEND_DIR / path
    if target.is_file():
        return send_from_directory(FRONTEND_DIR, path)
    return jsonify({"error": "not found"}), 404


if __name__ == "__main__":
    port = int(os.environ.get("PROXY_PORT", "8080"))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    print(f"CCF FL UI + API: http://127.0.0.1:{port}")
    print(f"CCF backend expected at: {CCF_SERVER}")
    print(
        "If your Mac browser cannot connect, use Cursor: "
        "Cmd+Shift+P -> 'Simple Browser: Show' -> "
        f"http://127.0.0.1:{port}"
    )
    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=False)
