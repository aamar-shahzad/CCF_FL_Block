#!/bin/bash
# Smoke test for CCFL FL API (run after: make run-virtual)
set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

CERT_DIR="${CERT_DIR:-.sandbox_ccf}"
BASE="https://127.0.0.1:8000/app"
CACERT="${CACERT:-./workspace/sandbox_common/service_cert.pem}"

if [ ! -f "$CACERT" ] && [ -f "$CERT_DIR/../workspace/sandbox_common/service_cert.pem" ]; then
  CACERT="$CERT_DIR/../workspace/sandbox_common/service_cert.pem"
fi

echo "Uploading initial model..."
MODEL_RESP=$(curl -sk -X POST "$BASE/model/intial_model" \
  -H "Content-Type: application/json" \
  -d '{"global_model":{"model_name":"smoke","model_data":{"layers":2}}}')
MODEL_ID=$(echo "$MODEL_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('model_id',0))" 2>/dev/null || echo "0")
echo "model_id=$MODEL_ID"

echo "Uploading local weights (user0)..."
curl -sk -X POST "$BASE/model/upload/local_model_weights" \
  --cert "$CERT_DIR/user0_cert.pem" --key "$CERT_DIR/user0_privk.pem" \
  -H "Content-Type: application/json" \
  -d "{\"model_id\":$MODEL_ID,\"round_no\":0,\"weights_json\":[0.1,0.2,0.3],\"client_id\":\"client_0\"}"

echo "Aggregating (member0, AHDA)..."
AGG=$(curl -sk -X PUT \
  "$BASE/model/aggregate_weights_local?model_id=$MODEL_ID&round_no=0&method=ahda" \
  --cert "$CERT_DIR/member0_cert.pem" --key "$CERT_DIR/member0_privk.pem")
echo "$AGG" | head -c 200
echo

echo "Downloading global weights..."
curl -sk "$BASE/model/download_gloabl_weights?model_id=$MODEL_ID" \
  --cert "$CERT_DIR/user0_cert.pem" --key "$CERT_DIR/user0_privk.pem" | head -c 200
echo

echo -e "${GREEN}Smoke test completed.${NC}"
