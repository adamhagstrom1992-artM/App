#!/usr/bin/env bash
# Startar Aktiekoll lokalt pa http://127.0.0.1:8000
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "Skapar virtuell miljo..."
  python3 -m venv .venv
  .venv/bin/pip install --quiet --upgrade pip
  .venv/bin/pip install --quiet -r requirements.txt
fi

exec .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
