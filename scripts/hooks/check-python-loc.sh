#!/usr/bin/env bash
# Check Python LOC ceiling (src)
# Reads limit from config/settings.yaml

set -e

# Read limit from config
LIMIT=$(PYTHONPATH=src uv run python -m vibe3.config.get \
    code_limits.total_file_loc.v3_python \
    -c config/settings.yaml \
    --quiet 2>/dev/null || echo 9000)

total=$(find src -name "*.py" | xargs cat | wc -l)

if [ "$total" -gt "$LIMIT" ]; then
  echo "FAIL: Total Python LOC $total exceeds $LIMIT limit"
  exit 1
else
  echo "✅ Total Python LOC: $total / $LIMIT"
fi