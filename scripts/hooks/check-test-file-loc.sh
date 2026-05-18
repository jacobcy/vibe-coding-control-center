#!/usr/bin/env bash
# Check per-file LOC ceiling for test files
# Reads limits from config/v3/loc_limits.yaml without uv
#
# Limits:
#   warning_threshold: 300 lines (advisory, suggests refactoring)
#   ci_block_threshold: 400 lines (enforced in CI, blocks pipeline)
#
# Test paths (defined in config/v3/loc_limits.yaml:code_limits.test_paths):
#   Python: tests/vibe3/
#
# Exit codes:
#   0: All files within default limit
#   1: Some files exceed max limit (or warnings with strict mode)

set -e

result=$(python3 - <<'PY'
from pathlib import Path
import sys

sys.path.insert(0, str(Path("scripts/hooks").resolve()))

from loc_settings import find_exception, iter_files, load_loc_settings


config = load_loc_settings()
warnings = 0
errors = 0

for file_path in iter_files(config.test_paths_v3_python, suffixes=(".py",), test_only=True):
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
        errors += 1
    elif exception is None and lines > config.warning_threshold:
        print(f"⚠️  WARNING: {rel_path} has {lines} lines")
        print(f"   Warning threshold: {config.warning_threshold} lines (local: advisory)")
        print(f"   CI block threshold: {config.ci_block_threshold} lines (CI: enforced)")
        print()
        print(f"   → Tip: Consider refactoring to under {config.warning_threshold} lines")
        warnings += 1

print()
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("Test file LOC check results:")
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
  echo "❌ BLOCKER: $errors test files exceed CI block threshold ($LIMIT_MAX lines)"

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
  echo "⚠️  ADVISORY: $warnings test files exceed warning threshold ($LIMIT_DEFAULT lines)"
  echo "   Local development: Suggestions only (push allowed)"
  echo "   CI will allow these files (under $LIMIT_MAX lines)"
  echo ""
  echo "💡 Tip: Consider refactoring for better maintainability"
else
  echo "✅ All test files within warning threshold ($LIMIT_DEFAULT lines)"
fi
