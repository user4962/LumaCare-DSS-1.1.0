#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$ROOT_DIR/.runtime"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_PYTHON="$BACKEND_DIR/.venv/bin/python"
VITE_BIN="$FRONTEND_DIR/node_modules/.bin/vite"
STARTUP_COMPLETE=false
mkdir -p "$RUNTIME_DIR"

fail() {
  echo "dev: $*" >&2
  exit 1
}

cleanup_incomplete_startup() {
  local exit_code=$?
  if [[ "$STARTUP_COMPLETE" != true ]]; then
    "$ROOT_DIR/scripts/stop.sh" --quiet >/dev/null 2>&1 || true
  fi
  return "$exit_code"
}

port_is_available() {
  "$BACKEND_PYTHON" - "$1" <<'PY'
import socket
import sys

port = int(sys.argv[1])
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
    probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        probe.bind(("127.0.0.1", port))
    except OSError:
        raise SystemExit(1)
PY
}

backend_identity_ready() {
  local health_payload
  local meta_payload
  health_payload="$(curl --silent --fail --max-time 1 http://127.0.0.1:8000/api/v1/health)" \
    || return 1
  meta_payload="$(curl --silent --fail --max-time 1 http://127.0.0.1:8000/api/v1/meta)" \
    || return 1
  "$BACKEND_PYTHON" -c '
import json
import sys

health = json.loads(sys.argv[1])
meta = json.loads(sys.argv[2])
valid = (
    health.get("status") == "ok"
    and health.get("database") == "ok"
    and meta.get("research_use_only") is True
    and meta.get("protocol_classification") == "research-demo"
    and meta.get("version") == health.get("version")
)
raise SystemExit(0 if valid else 1)
' "$health_payload" "$meta_payload"
}

frontend_identity_ready() {
  local html
  html="$(curl --silent --fail --max-time 1 "http://127.0.0.1:$FRONTEND_PORT/")" \
    || return 1
  [[ "$html" == *"<title>LumaCare DSS</title>"* && "$html" == *"/src/main.tsx"* ]]
}

[[ -x "$BACKEND_PYTHON" ]] \
  || fail "backend virtual environment is missing; run ./scripts/bootstrap.sh first"
[[ -x "$VITE_BIN" ]] \
  || fail "frontend dependencies are missing; run ./scripts/bootstrap.sh first"
command -v curl >/dev/null 2>&1 || fail "curl is required"
command -v ps >/dev/null 2>&1 || fail "ps is required"
command -v nohup >/dev/null 2>&1 || fail "nohup is required"

trap cleanup_incomplete_startup EXIT
"$ROOT_DIR/scripts/stop.sh" --quiet

port_is_available 8000 \
  || fail "API port 8000 is occupied by a process not managed by this workspace"

if port_is_available 5173; then
  FRONTEND_PORT=5173
elif port_is_available 4173; then
  FRONTEND_PORT=4173
else
  fail "frontend ports 5173 and 4173 are both occupied"
fi

(
  cd "$BACKEND_DIR"
  nohup "$BACKEND_PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 \
    >"$RUNTIME_DIR/backend.log" 2>&1 &
  printf '%s\n' "$!" >"$RUNTIME_DIR/backend.pid"
)

(
  cd "$FRONTEND_DIR"
  nohup "$VITE_BIN" --config "$FRONTEND_DIR/vite.config.ts" \
    --host 127.0.0.1 --port "$FRONTEND_PORT" \
    >"$RUNTIME_DIR/frontend.log" 2>&1 &
  printf '%s\n' "$!" >"$RUNTIME_DIR/frontend.pid"
)
printf '%s\n' "$FRONTEND_PORT" >"$RUNTIME_DIR/frontend.port"

for _ in {1..80}; do
  backend_pid="$(tr -d '[:space:]' < "$RUNTIME_DIR/backend.pid")"
  frontend_pid="$(tr -d '[:space:]' < "$RUNTIME_DIR/frontend.pid")"
  if ! kill -0 "$backend_pid" 2>/dev/null; then
    fail "backend exited during startup; inspect $RUNTIME_DIR/backend.log"
  fi
  if ! kill -0 "$frontend_pid" 2>/dev/null; then
    fail "frontend exited during startup; inspect $RUNTIME_DIR/frontend.log"
  fi
  if backend_identity_ready && frontend_identity_ready; then
    STARTUP_COMPLETE=true
    echo "LumaCare DSS 1.1.0 is running: http://127.0.0.1:$FRONTEND_PORT"
    echo "API documentation: http://127.0.0.1:8000/docs"
    exit 0
  fi
  sleep 0.25
done

fail "services did not pass identity checks; inspect $RUNTIME_DIR/backend.log and $RUNTIME_DIR/frontend.log"
