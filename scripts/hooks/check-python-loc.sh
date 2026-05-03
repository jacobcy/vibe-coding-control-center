#!/usr/bin/env bash
# Check Python LOC ceiling (core code only)
#
# Behavior:
#   - Local hooks (pre-commit/pre-push): WARNING ONLY (exit 0)
#   - CI: Set env var ENFORCE_LOC_LIMITS=true to BLOCK on violations
#
# Uses only the Python standard library so it can run before uv sync.
#
# Code paths (defined in config/loc_limits.yaml:code_limits.code_paths.v3_python):
#   - src/vibe3/ (including orchestra modules)
#
# Note: scripts/ NOT included in total LOC (checked separately for single-file limits only)

set -e

result=$(python3 - <<'PY'
from pathlib import Path
import sys

sys.path.insert(0, str(Path("scripts/hooks").resolve()))

from loc_settings import iter_files, load_loc_settings


config = load_loc_settings()
limit_total = config.total_v3_python
warning_threshold_percent = config.warning_threshold_percent

total_loc = 0
for path in iter_files(config.code_paths_v3_python, suffixes=(".py",)):
  if path.name == "__init__.py":
    continue
  total_loc += sum(1 for _ in path.open())

print(f"{total_loc} {limit_total} {warning_threshold_percent}")
PY
)

total=$(echo "$result" | awk '{print $1}')
LIMIT=$(echo "$result" | awk '{print $2}')
WARNING_PERCENT=$(echo "$result" | awk '{print $3}')

# Calculate warning threshold
WARNING_THRESHOLD=$((LIMIT * WARNING_PERCENT / 100))

# Determine alert level and output
percentage=$((total * 100 / LIMIT))

if [ "$total" -ge "$LIMIT" ]; then
  # RED: LOC exceeds limit
  echo "🔴 ALERT: Total Python LOC: $total / $LIMIT ($percentage%) - exceeds limit"
  echo ""
  echo "💡 Action required: Reduce code or adjust limit with justification"

  # In CI (ENFORCE_LOC_LIMITS=true), block on violations
  if [ "${ENFORCE_LOC_LIMITS:-false}" = "true" ]; then
    echo ""
    echo "❌ CI ENFORCEMENT: LOC limit exceeded - blocking pipeline"
    exit 1
  else
    echo ""
    echo "   Push allowed (local development)"
    exit 0
  fi
elif [ "$total" -ge "$WARNING_THRESHOLD" ]; then
  # YELLOW: LOC in warning zone
  echo "🟡 WARNING: Total Python LOC: $total / $LIMIT ($percentage%) - approaching limit"
  echo ""
  echo "💡 Tip: Review code for potential reductions before hitting limit"
  echo "   Warning threshold: $WARNING_THRESHOLD ($WARNING_PERCENT% of limit)"
  exit 0
else
  # GREEN: LOC below warning threshold
  echo "🟢 Total Python LOC: $total / $LIMIT ($percentage%)"
  exit 0
fi
