#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

fail() {
  echo "bootstrap: $*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "required command '$1' was not found in PATH"
}

resolve_command() {
  local candidate="$1"
  if [[ "$candidate" == */* ]]; then
    [[ -x "$candidate" ]] || return 1
    printf '%s\n' "$candidate"
  else
    command -v "$candidate"
  fi
}

require_command node
require_command npm
require_command curl
require_command nohup
require_command ps

NODE_VERSION="$(node -p 'process.versions.node')"
if ! node -e '
  const [major, minor] = process.versions.node.split(".").map(Number)
  const supported = (major === 22 && minor >= 12) || major > 22
  process.exit(supported ? 0 : 1)
'; then
  fail "Node.js $NODE_VERSION is unsupported; install Node.js >=22.12.0"
fi

if [[ -x "$BACKEND_DIR/.venv/bin/python" ]]; then
  PYTHON="$BACKEND_DIR/.venv/bin/python"
elif [[ -n "${PYTHON_BIN:-}" ]]; then
  PYTHON="$(resolve_command "$PYTHON_BIN")" \
    || fail "PYTHON_BIN='$PYTHON_BIN' does not identify an executable Python interpreter"
else
  PYTHON="$(resolve_command python3)" \
    || fail "Python 3 was not found; install Python >=3.11 or set PYTHON_BIN"
fi

if ! "$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
  fail "Python >=3.11 is required; selected interpreter: $PYTHON"
fi

if [[ ! -d "$BACKEND_DIR/.venv" ]]; then
  "$PYTHON" -m venv "$BACKEND_DIR/.venv"
fi

[[ -x "$BACKEND_DIR/.venv/bin/python" ]] \
  || fail "backend virtual environment is incomplete; remove backend/.venv and rerun bootstrap"
[[ -f "$BACKEND_DIR/requirements.txt" ]] || fail "backend/requirements.txt is missing"
[[ -f "$FRONTEND_DIR/package-lock.json" ]] \
  || fail "frontend/package-lock.json is required for reproducible npm installation"

echo "Using Python $("$BACKEND_DIR/.venv/bin/python" -c 'import platform; print(platform.python_version())')"
echo "Using Node.js $NODE_VERSION and npm $(npm --version)"

"$BACKEND_DIR/.venv/bin/python" -m pip install -r "$BACKEND_DIR/requirements.txt"
(cd "$FRONTEND_DIR" && npm ci)

echo "LumaCare DSS dependencies are installed."
