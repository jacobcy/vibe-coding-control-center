#!/usr/bin/env bash
# Check Python LOC ceiling
# Reads limit from config/settings.yaml
#
# Code paths (defined in config/settings.yaml:code_limits.code_paths.v3_python):
#   - src/vibe3/

set -e

# Read limit from config
LIMIT=$(PYTHONPATH=src uv run python -m vibe3.config.get \
    code_limits.total_file_loc.v3_python \
    -c config/settings.yaml \
    --quiet 2>/dev/null || echo 9000)

# Count total lines (paths defined in config: code_limits.code_paths.v3_python)
total=$(find src -name "*.py" | xargs cat | wc -l)

if [ "$total" -gt "$LIMIT" ]; then
  echo "FAIL: Total Python LOC $total exceeds $LIMIT limit"
  exit 1
else
  echo "✅ Total Python LOC: $total / $LIMIT"
fi