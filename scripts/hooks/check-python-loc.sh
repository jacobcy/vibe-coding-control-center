#!/usr/bin/env bash
# Check Python LOC ceiling (scripts/python)
# Reads limit from config/settings.yaml via Python config module

set -e

# Read limit from config
LIMIT=$(PYTHONPATH=scripts/python uv run python -m vibe3.config.get \
    code_limits.v3_python.total_loc \
    -c config/settings.yaml \
    --quiet 2>/dev/null || echo 7000)

total=$(find scripts/python -name "*.py" | xargs cat | wc -l)

if [ "$total" -gt "$LIMIT" ]; then
  echo "FAIL: Total Python LOC $total exceeds $LIMIT limit"
  exit 1
else
  echo "✅ Total Python LOC: $total / $LIMIT"
fi