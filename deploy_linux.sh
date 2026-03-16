#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
RUNTIME_DIR="$ROOT_DIR/runtime"
LOG_DIR="$ROOT_DIR/runtime_logs"
VENV_DIR="$BACKEND_DIR/.venv"
DIST_INDEX="$FRONTEND_DIR/dist/index.html"

PYTHON_BIN="${PYTHON_BIN:-python3}"
NPM_BIN="${NPM_BIN:-npm}"
USE_CONDA_ENV="${USE_CONDA_ENV:-0}"

mkdir -p "$RUNTIME_DIR" "$LOG_DIR"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python not found: $PYTHON_BIN" >&2
  exit 1
fi

if ! command -v "$NPM_BIN" >/dev/null 2>&1; then
  NPM_BIN=""
fi

if [ "$USE_CONDA_ENV" = "1" ]; then
  BACKEND_PYTHON="$PYTHON_BIN"
  BACKEND_PIP="$PYTHON_BIN -m pip"
else
  if [ ! -d "$VENV_DIR" ]; then
    "$PYTHON_BIN" -m venv "$VENV_DIR"
  fi

  BACKEND_PYTHON="$VENV_DIR/bin/python"
  BACKEND_PIP="$VENV_DIR/bin/pip"
fi

"$BACKEND_PYTHON" -m pip install --upgrade pip setuptools wheel
if [ "$USE_CONDA_ENV" = "1" ]; then
  $BACKEND_PIP install -r "$BACKEND_DIR/requirements.txt"
else
  "$BACKEND_PIP" install -r "$BACKEND_DIR/requirements.txt"
fi

frontend_built=0
if [ -n "$NPM_BIN" ] && command -v node >/dev/null 2>&1; then
  node_major="$(node -p "process.versions.node.split('.')[0]" 2>/dev/null || echo 0)"
  node_minor="$(node -p "process.versions.node.split('.')[1]" 2>/dev/null || echo 0)"
  if [ "$node_major" -gt 20 ] || { [ "$node_major" -eq 20 ] && [ "$node_minor" -ge 19 ]; }; then
    # The repository currently includes Windows-built node_modules. Reinstall on Linux.
    rm -rf "$FRONTEND_DIR/node_modules" "$FRONTEND_DIR/dist"
    "$NPM_BIN" --prefix "$FRONTEND_DIR" install
    "$NPM_BIN" --prefix "$FRONTEND_DIR" run build
    frontend_built=1
  fi
fi

if [ "$frontend_built" -ne 1 ] && [ ! -f "$DIST_INDEX" ]; then
  echo "Frontend build skipped and no prebuilt dist found: $DIST_INDEX" >&2
  echo "Provide a built frontend/dist from another machine, or run with Node >= 20.19." >&2
  exit 1
fi

if [ "$frontend_built" -ne 1 ]; then
  echo "Skipping frontend build. Reusing existing dist at: $FRONTEND_DIR/dist"
fi

cat <<EOF
Linux deployment completed.
Backend python: $BACKEND_PYTHON
Frontend build: $FRONTEND_DIR/dist
Start all services with:
  USE_CONDA_ENV=$USE_CONDA_ENV PYTHON_BIN="$PYTHON_BIN" bash "$ROOT_DIR/start_services.sh"
EOF
