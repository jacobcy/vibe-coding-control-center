#!/usr/bin/env bash
# Check Shell LOC ceiling (lib/ + bin/ + lib3/)
# Reads limit from config/settings.yaml via Python config module

set -e

# Read limit from config
LIMIT=$(PYTHONPATH=src uv run python -m vibe3.config.get \
    code_limits.v2_shell.total_loc \
    -c config/settings.yaml \
    --quiet 2>/dev/null || echo 7000)

total=$(find lib/ bin/ lib3/ -name "*.sh" -o -name "vibe" 2>/dev/null | xargs cat 2>/dev/null | wc -l)

if [ "$total" -gt "$LIMIT" ]; then
  echo "FAIL: Total Shell LOC $total exceeds $LIMIT limit"
  exit 1
else
  echo "✅ Total Shell LOC: $total / $LIMIT"
fi