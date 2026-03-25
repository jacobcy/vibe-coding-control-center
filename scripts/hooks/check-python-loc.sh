#!/usr/bin/env bash
# Check Python LOC ceiling (core code only)
#
# Behavior:
#   - Local hooks (pre-commit/pre-push): WARNING ONLY (exit 0)
#   - CI: Set env var ENFORCE_LOC_LIMITS=true to BLOCK on violations
#
# Delegates to metrics_service for consistent LOC counting.
#
# Code paths (defined in config/settings.yaml:code_limits.code_paths.v3_python):
#   - src/vibe3/
#
# Note: scripts/ NOT included in total LOC (checked separately for single-file limits only)

set -e

result=$(PYTHONPATH=src uv run python -c "
from vibe3.services.metrics_service import collect_python_metrics
m = collect_python_metrics()
print(f'{m.total_loc} {m.limit_total}')
" 2>/dev/null)

total=$(echo "$result" | awk '{print $1}')
LIMIT=$(echo "$result" | awk '{print $2}')

if [ "$total" -gt "$LIMIT" ]; then
  echo "⚠️  WARNING: Total Python LOC $total exceeds $LIMIT limit"
  echo "   This is a soft constraint in local development"
  echo ""
  echo "💡 Tip: Split large modules, extract utilities, remove dead code"

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
else
  echo "✅ Total Python LOC: $total / $LIMIT"
fi
