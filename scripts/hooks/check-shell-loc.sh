#!/usr/bin/env bash
# Check Shell LOC ceiling
# Reads limit from config/settings.yaml
#
# Code paths (defined in config/settings.yaml:code_limits.code_paths.v2_shell):
#   - lib/
#   - lib3/
#   - bin/vibe

set -e

# Read limit from config
LIMIT=$(PYTHONPATH=src uv run python -m vibe3.config.get \
    code_limits.total_file_loc.v2_shell \
    -c config/settings.yaml \
    --quiet 2>/dev/null || echo 7000)

# Count total lines (paths defined in config: code_limits.code_paths.v2_shell)
total=$(find lib/ bin/ lib3/ -name "*.sh" -o -name "vibe" 2>/dev/null | xargs cat 2>/dev/null | wc -l)

if [ "$total" -gt "$LIMIT" ]; then
  echo "FAIL: Total Shell LOC $total exceeds $LIMIT limit"
  exit 1
else
  echo "✅ Total Shell LOC: $total / $LIMIT"
fi