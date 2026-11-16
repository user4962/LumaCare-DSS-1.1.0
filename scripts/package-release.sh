#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RELEASE_VERSION="1.1.0"
RELEASE_NAME="LumaCare-DSS-$RELEASE_VERSION"
OUTPUT_DIR="${1:-${LUMACARE_OUTPUT_DIR:-$ROOT_DIR/../outputs}}"

if [[ $# -gt 1 ]]; then
  echo "Usage: $0 [output-directory]" >&2
  exit 2
fi

fail() {
  echo "package-release: $*" >&2
  exit 1
}

command -v zip >/dev/null 2>&1 || fail "zip is required"
command -v awk >/dev/null 2>&1 || fail "awk is required"
if command -v shasum >/dev/null 2>&1; then
  HASH_COMMAND="shasum"
elif command -v sha256sum >/dev/null 2>&1; then
  HASH_COMMAND="sha256sum"
else
  fail "shasum or sha256sum is required"
fi

VERIFY_PYTHON="$ROOT_DIR/backend/.venv/bin/python"
[[ -x "$VERIFY_PYTHON" ]] \
  || fail "backend virtual environment is required; run ./scripts/bootstrap.sh first"
if ! "$VERIFY_PYTHON" - "$ROOT_DIR" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
summary_path = root / "evaluation" / "results" / "evaluation_summary.json"
if not summary_path.is_file():
    print("evaluation summary is missing", file=sys.stderr)
    raise SystemExit(1)

summary = json.loads(summary_path.read_text(encoding="utf-8"))
digest = hashlib.sha256()
for path in sorted((root / "backend" / "app" / "engine").glob("*.py")):
    digest.update(path.name.encode("utf-8"))
    digest.update(path.read_bytes())

valid = (
    summary.get("engine_sha256") == digest.hexdigest()
    and summary.get("scenario_count", 0) > 0
    and summary.get("passed_scenarios") == summary.get("scenario_count")
    and summary.get("deterministic_scenarios") == summary.get("scenario_count")
)
if not valid:
    print("evaluation results are stale or contain a failed requirement", file=sys.stderr)
    raise SystemExit(1)
PY
then
  fail "run ./scripts/test-all.sh before packaging"
fi

mkdir -p "$OUTPUT_DIR"
OUTPUT_DIR="$(cd "$OUTPUT_DIR" && pwd)"
STAGING_DIR="$(mktemp -d "${TMPDIR:-/tmp}/lumacare-release.XXXXXX")"
RELEASE_ROOT="$STAGING_DIR/$RELEASE_NAME"
ARCHIVE_PATH="$OUTPUT_DIR/$RELEASE_NAME.zip"
CHECKSUM_PATH="$ARCHIVE_PATH.sha256"
mkdir -p "$RELEASE_ROOT"

cleanup() {
  rm -rf "$STAGING_DIR"
}
trap cleanup EXIT

copy_required() {
  local relative_path="$1"
  local source_path="$ROOT_DIR/$relative_path"
  local destination_path="$RELEASE_ROOT/$relative_path"
  [[ -e "$source_path" ]] || fail "required release path is missing: $relative_path"
  mkdir -p "$(dirname "$destination_path")"
  cp -pR "$source_path" "$destination_path"
}

# This allow-list intentionally excludes installed dependencies, databases,
# runtime logs, generated frontend bundles, and local environment overrides.
RELEASE_PATHS=(
  ".env.example"
  "CHANGELOG.md"
  ".gitignore"
  "LumaCare-DSS.code-workspace"
  "README.md"
  "backend/.gitignore"
  "backend/README.md"
  "backend/app"
  "backend/pyproject.toml"
  "backend/requirements.txt"
  "backend/tests"
  "docs"
  "evaluation/README.md"
  "evaluation/run_evaluation.py"
  "evaluation/results/evaluation_summary.json"
  "evaluation/results/scenario_results.csv"
  "frontend/.gitignore"
  "frontend/eslint.config.js"
  "frontend/index.html"
  "frontend/package-lock.json"
  "frontend/package.json"
  "frontend/src"
  "frontend/tsconfig.app.json"
  "frontend/tsconfig.json"
  "frontend/tsconfig.node.json"
  "frontend/vite.config.ts"
  "scripts"
)

for relative_path in "${RELEASE_PATHS[@]}"; do
  copy_required "$relative_path"
done

if [[ -d "$ROOT_DIR/frontend/public" ]]; then
  copy_required "frontend/public"
fi

find "$RELEASE_ROOT" -type d \( \
  -name .venv -o -name node_modules -o -name dist -o -name .runtime \
  -o -name __pycache__ -o -name .pytest_cache -o -name coverage \
\) -prune -exec rm -rf {} +

find "$RELEASE_ROOT" -type f \( \
  -name '.env' -o -name '*.db' -o -name '*.db-*' -o -name '*.log' \
  -o -name '*.pid' -o -name '*.pyc' -o -name '*.pyo' \
  -o -name '*.tsbuildinfo' -o -name 'vite.config.js' -o -name 'vite.config.d.ts' \
\) -delete

FORBIDDEN_PATH="$(find "$RELEASE_ROOT" \( \
  -name .venv -o -name node_modules -o -name dist -o -name .runtime \
  -o -name '*.db' -o -name '*.db-*' -o -name '*.log' -o -name '*.pid' \
\) -print -quit)"
[[ -z "$FORBIDDEN_PATH" ]] || fail "forbidden runtime artifact reached staging: $FORBIDDEN_PATH"

MACHINE_SPECIFIC_PATH=""
while IFS= read -r candidate; do
  if LC_ALL=C grep -I -E '/Users/[^/]+|Documents/Codex' "$candidate" >/dev/null 2>&1; then
    MACHINE_SPECIFIC_PATH="$candidate"
    break
  fi
done < <(find "$RELEASE_ROOT" -type f ! -path "$RELEASE_ROOT/scripts/package-release.sh")
[[ -z "$MACHINE_SPECIFIC_PATH" ]] \
  || fail "a machine-specific absolute path was found in: $MACHINE_SPECIFIC_PATH"

rm -f "$ARCHIVE_PATH" "$CHECKSUM_PATH"
(cd "$STAGING_DIR" && zip -qr "$ARCHIVE_PATH" "$RELEASE_NAME")
zip -T "$ARCHIVE_PATH" >/dev/null

if [[ "$HASH_COMMAND" == "shasum" ]]; then
  DIGEST="$(shasum -a 256 "$ARCHIVE_PATH" | awk '{print $1}')"
else
  DIGEST="$(sha256sum "$ARCHIVE_PATH" | awk '{print $1}')"
fi
printf '%s  %s\n' "$DIGEST" "$(basename "$ARCHIVE_PATH")" >"$CHECKSUM_PATH"

echo "Release archive: $ARCHIVE_PATH"
echo "SHA-256 file:   $CHECKSUM_PATH"
