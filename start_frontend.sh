#!/usr/bin/env bash
set -euo pipefail

USE_VITE_DEV=0
if [ "${1:-}" = "--dev" ]; then
  USE_VITE_DEV=1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
NPM_BIN="${NPM_BIN:-npm}"
USE_CONDA_ENV="${USE_CONDA_ENV:-0}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

if [ "$USE_CONDA_ENV" = "1" ]; then
  BACKEND_PYTHON="$PYTHON_BIN"
else
  BACKEND_PYTHON="$ROOT_DIR/backend/.venv/bin/python"
fi

if [ ! -x "$BACKEND_PYTHON" ]; then
  echo "Backend python not found: $BACKEND_PYTHON" >&2
  echo "Run: USE_CONDA_ENV=$USE_CONDA_ENV PYTHON_BIN=\"$PYTHON_BIN\" bash \"$ROOT_DIR/deploy_linux.sh\"" >&2
  exit 1
fi

if [ "$USE_VITE_DEV" -eq 1 ]; then
  cd "$FRONTEND_DIR"
  if [ ! -d node_modules ]; then
    "$NPM_BIN" install
  fi
  exec "$NPM_BIN" run dev -- --host 0.0.0.0 --port "$FRONTEND_PORT" --strictPort
fi

if [ ! -f "$FRONTEND_DIR/dist/index.html" ]; then
  echo "Frontend dist not found. Run: bash \"$ROOT_DIR/deploy_linux.sh\"" >&2
  exit 1
fi

cd "$ROOT_DIR"
exec "$BACKEND_PYTHON" -m uvicorn frontend_proxy_server:app --host 0.0.0.0 --port "$FRONTEND_PORT"
