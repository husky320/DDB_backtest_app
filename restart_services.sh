#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USE_CONDA_ENV="${USE_CONDA_ENV:-0}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

env FRONTEND_PORT="$FRONTEND_PORT" bash "$ROOT_DIR/stop_services.sh"
sleep 1
env USE_CONDA_ENV="$USE_CONDA_ENV" PYTHON_BIN="$PYTHON_BIN" FRONTEND_PORT="$FRONTEND_PORT" bash "$ROOT_DIR/start_services.sh"
