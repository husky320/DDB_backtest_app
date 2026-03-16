#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_DIR="$ROOT_DIR/runtime"
LOG_DIR="$ROOT_DIR/runtime_logs"
PID_FILE="$RUNTIME_DIR/service_pids.json"
USE_CONDA_ENV="${USE_CONDA_ENV:-0}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

mkdir -p "$RUNTIME_DIR" "$LOG_DIR"

is_healthy() {
  local url="$1"
  python3 - "$url" <<'PY'
import sys
import urllib.error
import urllib.request

url = sys.argv[1]
try:
    with urllib.request.urlopen(url, timeout=2) as resp:
        sys.exit(0 if 200 <= resp.status < 500 else 1)
except Exception:
    sys.exit(1)
PY
}

wait_endpoint() {
  local url="$1"
  local timeout="${2:-180}"
  local i
  for ((i=0; i<timeout; i++)); do
    if is_healthy "$url"; then
      return 0
    fi
    sleep 1
  done
  return 1
}

port_pids() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true
    return
  fi
  if command -v ss >/dev/null 2>&1; then
    ss -ltnp "( sport = :$port )" 2>/dev/null | awk -F 'pid=' 'NR>1 && NF>1 {split($2,a,","); print a[1]}' | sort -u
    return
  fi
  echo "Neither lsof nor ss is available to inspect listening ports." >&2
  return 1
}

stop_pid() {
  local pid="$1"
  [ -n "$pid" ] || return 0
  kill "$pid" 2>/dev/null || true
  sleep 0.2
  kill -9 "$pid" 2>/dev/null || true
}

backend_pids="$(port_pids 8000 || true)"
if [ -n "$backend_pids" ] && ! is_healthy "http://127.0.0.1:8000/health"; then
  while read -r pid; do
    [ -n "$pid" ] && stop_pid "$pid"
  done <<< "$backend_pids"
fi

frontend_pids="$(port_pids "$FRONTEND_PORT" || true)"
if [ -n "$frontend_pids" ] && ! is_healthy "http://127.0.0.1:$FRONTEND_PORT"; then
  while read -r pid; do
    [ -n "$pid" ] && stop_pid "$pid"
  done <<< "$frontend_pids"
fi

backend_pid=""
if is_healthy "http://127.0.0.1:8000/health"; then
  backend_pid="$(printf '%s\n' "$backend_pids" | head -n 1)"
else
  nohup env USE_CONDA_ENV="$USE_CONDA_ENV" PYTHON_BIN="$PYTHON_BIN" bash "$ROOT_DIR/start_backend.sh" >"$LOG_DIR/backend.out.log" 2>"$LOG_DIR/backend.err.log" &
  backend_pid="$!"
fi

frontend_pid=""
if is_healthy "http://127.0.0.1:$FRONTEND_PORT"; then
  frontend_pid="$(printf '%s\n' "$frontend_pids" | head -n 1)"
else
  nohup env USE_CONDA_ENV="$USE_CONDA_ENV" PYTHON_BIN="$PYTHON_BIN" FRONTEND_PORT="$FRONTEND_PORT" bash "$ROOT_DIR/start_frontend.sh" >"$LOG_DIR/frontend.out.log" 2>"$LOG_DIR/frontend.err.log" &
  frontend_pid="$!"
fi

backend_ok=0
frontend_ok=0
wait_endpoint "http://127.0.0.1:8000/health" 180 && backend_ok=1
wait_endpoint "http://127.0.0.1:$FRONTEND_PORT" 180 && frontend_ok=1

cat >"$PID_FILE" <<EOF
{
  "backend_pid": ${backend_pid:-null},
  "frontend_pid": ${frontend_pid:-null},
  "started_at": "$(date '+%Y-%m-%dT%H:%M:%S%z')"
}
EOF

echo "backend_ok=$backend_ok"
echo "frontend_ok=$frontend_ok"
echo "backend_pid=${backend_pid:-}"
echo "frontend_pid=${frontend_pid:-}"
echo "backend_url=http://127.0.0.1:8000/docs"
echo "frontend_url=http://127.0.0.1:$FRONTEND_PORT/factors"
echo "pid_file=$PID_FILE"

if [ "$backend_ok" -ne 1 ] || [ "$frontend_ok" -ne 1 ]; then
  echo "One or more services failed to become healthy in time." >&2
  exit 1
fi
