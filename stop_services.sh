#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_DIR="$ROOT_DIR/runtime"
PID_FILE="$RUNTIME_DIR/service_pids.json"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

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
}

force_stop_pid() {
  local pid="$1"
  [ -n "$pid" ] || return 0
  kill -9 "$pid" 2>/dev/null || true
}

wait_port_closed() {
  local port="$1"
  local timeout="${2:-12}"
  local i
  for ((i=0; i<timeout; i++)); do
    if [ -z "$(port_pids "$port" || true)" ]; then
      return 0
    fi
    sleep 1
  done
  return 1
}

curl -fsS -m 2 -X POST "http://127.0.0.1:8000/api/dolphindb/system/shutdown" >/dev/null 2>&1 || true
sleep 1

if [ -f "$PID_FILE" ]; then
  backend_pid="$(python3 - "$PID_FILE" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    payload = {}
print(payload.get("backend_pid", ""))
PY
)"
  frontend_pid="$(python3 - "$PID_FILE" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    payload = {}
print(payload.get("frontend_pid", ""))
PY
)"
  stop_pid "$backend_pid"
  stop_pid "$frontend_pid"
fi

for pid in $(port_pids 8000 || true) $(port_pids "$FRONTEND_PORT" || true); do
  stop_pid "$pid"
done

wait_port_closed 8000 12 || true
wait_port_closed "$FRONTEND_PORT" 12 || true

for pid in $(port_pids 8000 || true) $(port_pids "$FRONTEND_PORT" || true); do
  force_stop_pid "$pid"
done

rm -f "$PID_FILE"

if [ -z "$(port_pids 8000 || true)" ]; then
  echo "backend_stopped=true"
else
  echo "backend_stopped=false"
fi

if [ -z "$(port_pids "$FRONTEND_PORT" || true)" ]; then
  echo "frontend_stopped=true"
else
  echo "frontend_stopped=false"
fi
