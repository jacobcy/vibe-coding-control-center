#!/usr/bin/env bash
# Check Python LOC ceiling (core code only)
# Reads limit from config/settings.yaml
#
# Code paths (defined in config/settings.yaml:code_limits.code_paths.v3_python):
#   - src/vibe3/
#
# Note: scripts/ NOT included in total LOC (checked separately for single-file limits only)

set -e

# Read limit from config
LIMIT=$(PYTHONPATH=src uv run python -m vibe3.config.get \
    code_limits.total_file_loc.v3_python \
    -c config/settings.yaml \
    --quiet 2>/dev/null || echo 9000)

# Count total lines (paths defined in config: code_limits.code_paths.v3_python)
# Only src/vibe3/ (scripts/ NOT included)
total=$(find src/vibe3 -name "*.py" 2>/dev/null | xargs cat 2>/dev/null | wc -l)

if [ "$total" -gt "$LIMIT" ]; then
  echo "FAIL: Total Python LOC $total exceeds $LIMIT limit"
  exit 1
else
  echo "✅ Total Python LOC: $total / $LIMIT"
fi