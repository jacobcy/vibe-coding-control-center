#!/usr/bin/env bash
# Check Shell LOC ceiling (core code only)
#
# Behavior:
#   - Local hooks (pre-commit/pre-push): WARNING ONLY (exit 0)
#   - CI: Set env var ENFORCE_LOC_LIMITS=true to BLOCK on violations
#
# Delegates to shell_metrics_collector for consistent LOC counting.
#
# Code paths (defined in config/settings.yaml:code_limits.code_paths.v2_shell):
#   - lib/
#   - lib3/
#   - bin/vibe
#
# Note: scripts/ NOT included in total LOC (checked separately for single-file limits only)

set -e

result=$(PYTHONPATH=src uv run python -c "
from vibe3.services.shell_metrics_collector import collect_shell_metrics
m = collect_shell_metrics()
print(f'{m.total_loc} {m.limit_total}')
" 2>/dev/null)

total=$(echo "$result" | awk '{print $1}')
LIMIT=$(echo "$result" | awk '{print $2}')

if [ "$total" -gt "$LIMIT" ]; then
  echo "⚠️  WARNING: Total Shell LOC $total exceeds $LIMIT limit"
  echo "   This is a soft constraint in local development"
  echo ""
  echo "💡 Tip: Split large functions, remove dead code, use libraries"

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
  echo "✅ Total Shell LOC: $total / $LIMIT"
fi
