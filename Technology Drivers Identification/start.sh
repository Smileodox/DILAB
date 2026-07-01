#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
else
  source venv/bin/activate
fi

if [ ! -f ".env" ]; then
  echo "Copy .env.example to .env and set OPENROUTER_API_KEY first."
  exit 1
fi

uvicorn api:app --reload --host 127.0.0.1 --port 8002
