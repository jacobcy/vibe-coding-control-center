#!/usr/bin/env bash
# Check per-file LOC ceiling for source files
#
# Behavior:
#   - Local hooks (pre-commit/pre-push): WARNING ONLY (exit 0)
#   - CI: Set env var ENFORCE_LOC_LIMITS=true to BLOCK on violations
#
# Reads limits from config/v3/loc_limits.yaml without uv
#
# Limits (unified for all file types):
#   warning_threshold: 300 lines (advisory, suggests refactoring)
#   ci_block_threshold: 400 lines (enforced in CI, blocks pipeline)

#
# Code paths (defined in config/v3/loc_limits.yaml:code_limits.code_paths):
#   Shell: lib/, lib3/, bin/vibe
#   Python: src/vibe3/
#
# Scripts paths (defined in config/v3/loc_limits.yaml:code_limits.scripts_paths):
#   Shell: scripts/ (*.sh files)
#   Python: scripts/ (*.py files)
#
# Note: scripts/ are checked for single-file limits but NOT counted in total LOC

set -e

result=$(python3 - <<'PY'
from pathlib import Path
import sys

sys.path.insert(0, str(Path("scripts/hooks").resolve()))

from loc_settings import find_exception, iter_files, load_loc_settings


config = load_loc_settings()
warnings = 0
errors = 0

files = {
    path.as_posix(): path
    for path in (
        iter_files(config.code_paths_v2_shell, suffixes=(".sh",))
        + iter_files(config.code_paths_v3_python, suffixes=(".py",))
        + iter_files(config.scripts_paths_v2_shell, suffixes=(".sh",))
        + iter_files(config.scripts_paths_v3_python, suffixes=(".py",))
    )
}
for file_path in [files[key] for key in sorted(files)]:
    if file_path.name == "__init__.py":
        continue

    rel_path = file_path.as_posix()
    lines = sum(1 for _ in file_path.open())
    exception = find_exception(config.exceptions, rel_path)
    limit = exception.limit if exception else config.ci_block_threshold

    if lines > limit:
        label = f"custom: {limit}" if exception else f"ci_block: {config.ci_block_threshold}"
        print(f"❌ CI BLOCK: {rel_path} has {lines} lines")
        if exception:
            print(f"   Custom limit: {limit} lines (exception granted)")
        else:
            print(f"   Warning threshold: {config.warning_threshold} lines (local: advisory)")
            print(f"   CI block threshold: {config.ci_block_threshold} lines (CI: enforced)")
            print()
            print(f"   → Action: This file will block CI. Options:")
            print(f"     1. Refactor to under {config.ci_block_threshold} lines")
            print(f"     2. Request exception in config/v3/loc_limits.yaml")
        print()  # Separate files
        errors += 1
    elif exception is None and lines > config.warning_threshold:
        print(f"⚠️  WARNING: {rel_path} has {lines} lines")
        print(f"   Warning threshold: {config.warning_threshold} lines (local: advisory)")
        print(f"   CI block threshold: {config.ci_block_threshold} lines (CI: enforced)")
        print()
        print(f"   → Tip: Consider refactoring to under {config.warning_threshold} lines")
        print()  # Separate files
        warnings += 1

print()
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("Source file LOC check results:")
print(f"  - Warning threshold: {config.warning_threshold} lines (advisory)")
print(f"  - CI block threshold: {config.ci_block_threshold} lines (enforced)")
print(f"  - Warnings: {warnings} files (threshold exceeded)")
print(f"  - Errors: {errors} files (CI will block)")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print(f"COUNTS {warnings} {errors} {config.warning_threshold} {config.ci_block_threshold}")
PY
)

echo "$result" | sed '$d'

COUNTS_LINE=$(echo "$result" | tail -n 1)
warnings=$(echo "$COUNTS_LINE" | awk '{print $2}')
errors=$(echo "$COUNTS_LINE" | awk '{print $3}')
LIMIT_DEFAULT=$(echo "$COUNTS_LINE" | awk '{print $4}')
LIMIT_MAX=$(echo "$COUNTS_LINE" | awk '{print $5}')

if [ "$errors" -gt 0 ]; then
  echo ""
  echo "❌ BLOCKER: $errors files exceed CI block threshold ($LIMIT_MAX lines)"

  # In CI (ENFORCE_LOC_LIMITS=true), block on violations
  if [ "${ENFORCE_LOC_LIMITS:-false}" = "true" ]; then
    echo ""
    echo "   CI enforcement mode: BLOCKING pipeline"
    echo "   These files must be refactored or granted exceptions before merge"
    exit 1
  else
    echo ""
    echo "   Local development mode: Advisory only"
    echo "   These files will block CI - address before pushing"
    echo ""
    echo "💡 Options:"
    echo "   1. Refactor to under $LIMIT_MAX lines"
    echo "   2. Request exception in config/v3/loc_limits.yaml"
    exit 0
  fi
elif [ "$warnings" -gt 0 ]; then
  echo ""
  echo "⚠️  ADVISORY: $warnings files exceed warning threshold ($LIMIT_DEFAULT lines)"
  echo "   Local development: Suggestions only (push allowed)"
  echo "   CI will allow these files (under $LIMIT_MAX lines)"
  echo ""
  echo "💡 Tip: Consider refactoring for better maintainability"
else
  echo "✅ All source files within warning threshold ($LIMIT_DEFAULT lines)"
fi
