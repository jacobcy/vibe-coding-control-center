#!/usr/bin/env bash
# Check Shell LOC ceiling (core code only)
# Delegates to metrics_service for consistent LOC counting.
#
# Code paths (defined in config/settings.yaml:code_limits.code_paths.v2_shell):
#   - lib/
#   - lib3/
#   - bin/vibe
#
# Note: scripts/ NOT included in total LOC (checked separately for single-file limits only)

set -e

result=$(PYTHONPATH=src uv run python -c "
from vibe3.services.metrics_service import collect_shell_metrics
m = collect_shell_metrics()
print(f'{m.total_loc} {m.limit_total}')
" 2>/dev/null)

total=$(echo "$result" | awk '{print $1}')
LIMIT=$(echo "$result" | awk '{print $2}')

if [ "$total" -gt "$LIMIT" ]; then
  echo "FAIL: Total Shell LOC $total exceeds $LIMIT limit"
  exit 1
else
  echo "✅ Total Shell LOC: $total / $LIMIT"
fi
