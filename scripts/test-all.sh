#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_PYTHON="$ROOT_DIR/backend/.venv/bin/python"
EVALUATION_ITERATIONS="${LUMACARE_EVAL_ITERATIONS:-50000}"

[[ -x "$BACKEND_PYTHON" ]] || {
  echo "test-all: backend virtual environment is missing; run ./scripts/bootstrap.sh first" >&2
  exit 1
}
[[ -d "$ROOT_DIR/frontend/node_modules" ]] || {
  echo "test-all: frontend dependencies are missing; run ./scripts/bootstrap.sh first" >&2
  exit 1
}
[[ "$EVALUATION_ITERATIONS" =~ ^[0-9]+$ && "$EVALUATION_ITERATIONS" -ge 100 ]] || {
  echo "test-all: LUMACARE_EVAL_ITERATIONS must be an integer of at least 100" >&2
  exit 2
}

echo "[1/8] Checking Python dependency consistency"
(cd "$ROOT_DIR/backend" && ./.venv/bin/python -m pip check)

echo "[2/8] Auditing Python dependencies"
(cd "$ROOT_DIR/backend" && ./.venv/bin/python -m pip_audit --local --progress-spinner off)

echo "[3/8] Running backend unit and API integration tests"
(cd "$ROOT_DIR/backend" && ./.venv/bin/python -m pytest -q)

echo "[4/8] Running the deterministic requirements matrix ($EVALUATION_ITERATIONS iterations)"
"$BACKEND_PYTHON" "$ROOT_DIR/evaluation/run_evaluation.py" \
  --iterations "$EVALUATION_ITERATIONS"

echo "[5/8] Auditing frontend dependencies"
(cd "$ROOT_DIR/frontend" && npm audit)

echo "[6/8] Running frontend component and mapping tests"
(cd "$ROOT_DIR/frontend" && npm run test)

echo "[7/8] Running frontend lint"
(cd "$ROOT_DIR/frontend" && npm run lint)

echo "[8/8] Running TypeScript checks and the production build"
(cd "$ROOT_DIR/frontend" && npm run build)

echo "All automated verification, audit, evaluation, lint, and build gates passed."
