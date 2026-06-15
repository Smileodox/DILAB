#!/usr/bin/env bash
set -euo pipefail

SUBSCRIPTION="381a8ac7-d113-4a6b-8a54-f5cddac177b1"  # Vehicle Aftermarket - FRA
RG="rg-chatbot-poc"
PLAN="asp-chatbot-poc"
APP="dilab-foresight"
PYTHON="3.12"

cd "$(dirname "$0")/.."
ROOT=$(pwd)

echo "=== 0/5 Subscription ==="
az account set --subscription "$SUBSCRIPTION"

echo "=== 1/5 Resource Group ==="
echo "  Using existing: $RG / $PLAN"

echo "=== 2/5 Web App ==="
az webapp create \
  --name "$APP" \
  --resource-group "$RG" \
  --plan "$PLAN" \
  --runtime "PYTHON:${PYTHON}" \
  -o none 2>/dev/null || echo "  (app may already exist, continuing)"

az webapp config set \
  --name "$APP" \
  --resource-group "$RG" \
  --startup-file "gunicorn --bind 0.0.0.0:8000 --worker-class uvicorn.workers.UvicornWorker --timeout 120 web.app:app" \
  -o none

echo "=== 4/5 Building ZIP ==="
TMPZIP=$(mktemp /tmp/dilab-deploy-XXXXXX.zip)
rm -f "$TMPZIP"

# Include: web app + static build + data JSONs + requirements
zip -r "$TMPZIP" \
  web/app.py \
  web/static/ \
  data/outputs/ \
  requirements-web.txt \
  -x "web/frontend/*" "web/static/.DS_Store" "*.pyc" "__pycache__/*"

# Azure expects requirements.txt at root
cd /tmp
mkdir -p _dilab_deploy && cd _dilab_deploy
cp "$ROOT/requirements-web.txt" requirements.txt
zip -u "$TMPZIP" requirements.txt
rm -rf /tmp/_dilab_deploy

echo "  ZIP: $(du -h "$TMPZIP" | cut -f1)"

echo "=== 5/5 Deploying ==="
az webapp deploy \
  --name "$APP" \
  --resource-group "$RG" \
  --src-path "$TMPZIP" \
  --type zip \
  --timeout 600

rm -f "$TMPZIP"

URL="https://${APP}.azurewebsites.net"
echo ""
echo "=== Deployed ==="
echo "  URL: $URL"
echo "  Logs: az webapp log tail --name $APP --resource-group $RG"
