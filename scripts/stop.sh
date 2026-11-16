#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$ROOT_DIR/.runtime"
QUIET=false
STOP_FAILED=false

if [[ "${1:-}" == "--quiet" ]]; then
  QUIET=true
elif [[ $# -gt 0 ]]; then
  echo "Usage: $0 [--quiet]" >&2
  exit 2
fi

log() {
  if [[ "$QUIET" != true ]]; then
    echo "$*"
  fi
}

warn() {
  echo "stop: $*" >&2
}

process_matches_service() {
  local service="$1"
  local pid="$2"
  local command_line
  command_line="$(ps -ww -p "$pid" -o command= 2>/dev/null || true)"
  case "$service" in
    backend)
      [[ "$command_line" == *"$ROOT_DIR/backend/.venv/bin/python"* \
        && "$command_line" == *"uvicorn app.main:app"* \
        && "$command_line" == *"--port 8000"* ]]
      ;;
    frontend)
      [[ ( "$command_line" == *"$ROOT_DIR/frontend/node_modules/.bin/vite"* \
          || "$command_line" == *"$ROOT_DIR/frontend/node_modules/vite/bin/vite.js"* ) \
        && "$command_line" == *"$ROOT_DIR/frontend/vite.config.ts"* \
        && "$command_line" == *"--host 127.0.0.1"* ]]
      ;;
    *)
      return 1
      ;;
  esac
}

for service in backend frontend; do
  pid_file="$RUNTIME_DIR/$service.pid"
  [[ -f "$pid_file" ]] || continue

  pid="$(tr -d '[:space:]' < "$pid_file")"
  if [[ ! "$pid" =~ ^[0-9]+$ || "$pid" -le 1 ]]; then
    warn "discarding invalid $service PID file: $pid_file"
    rm -f "$pid_file"
    continue
  fi

  if ! kill -0 "$pid" 2>/dev/null; then
    rm -f "$pid_file"
    continue
  fi

  if ! process_matches_service "$service" "$pid"; then
    warn "PID $pid no longer matches the recorded $service command; it was not terminated"
    rm -f "$pid_file"
    continue
  fi

  if ! kill "$pid" 2>/dev/null; then
    rm -f "$pid_file"
    continue
  fi
  for _ in {1..50}; do
    if ! kill -0 "$pid" 2>/dev/null; then
      break
    fi
    sleep 0.1
  done

  if kill -0 "$pid" 2>/dev/null; then
    if process_matches_service "$service" "$pid"; then
      warn "$service PID $pid did not stop after 5 seconds; sending SIGKILL"
      kill -KILL "$pid" 2>/dev/null || true
      for _ in {1..10}; do
        if ! kill -0 "$pid" 2>/dev/null; then
          break
        fi
        sleep 0.1
      done
    fi
  fi

  if kill -0 "$pid" 2>/dev/null; then
    warn "$service PID $pid is still running"
    STOP_FAILED=true
  else
    rm -f "$pid_file"
  fi
done

if [[ "$STOP_FAILED" == true ]]; then
  exit 1
fi

rm -f "$RUNTIME_DIR/frontend.port"
log "LumaCare DSS services are stopped."
