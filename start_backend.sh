#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
USE_CONDA_ENV="${USE_CONDA_ENV:-0}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [ "$USE_CONDA_ENV" = "1" ]; then
  BACKEND_PYTHON="$PYTHON_BIN"
else
  BACKEND_PYTHON="$BACKEND_DIR/.venv/bin/python"
fi

if [ ! -x "$BACKEND_PYTHON" ]; then
  echo "Backend python not found: $BACKEND_PYTHON" >&2
  echo "Run: USE_CONDA_ENV=$USE_CONDA_ENV PYTHON_BIN=\"$PYTHON_BIN\" bash \"$ROOT_DIR/deploy_linux.sh\"" >&2
  exit 1
fi

cd "$BACKEND_DIR"
exec "$BACKEND_PYTHON" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
