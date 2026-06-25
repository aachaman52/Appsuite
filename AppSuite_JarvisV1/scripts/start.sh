#!/usr/bin/env bash
# Start the AppSuite REST API server.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

python scripts/init_db.py
echo "Starting AppSuite on http://0.0.0.0:8000 (docs at /docs)"
exec python -m appsuite.main