#!/usr/bin/env bash
# Check Shell LOC ceiling (core code only)
# Reads limit from config/settings.yaml
#
# Code paths (defined in config/settings.yaml:code_limits.code_paths.v2_shell):
#   - lib/
#   - lib3/
#   - bin/vibe
#
# Note: scripts/ NOT included in total LOC (checked separately for single-file limits only)

set -e

# Read limit from config
LIMIT=$(PYTHONPATH=src uv run python -m vibe3.config.get \
    code_limits.total_file_loc.v2_shell \
    -c config/settings.yaml \
    --quiet 2>/dev/null || echo 7000)

# Count total lines (paths defined in config: code_limits.code_paths.v2_shell)
# Only lib/, lib3/, bin/vibe (scripts/ NOT included)
total=$( (find lib/ lib3/ -name "*.sh" 2>/dev/null; \
          find bin/ -name "vibe" 2>/dev/null) | \
        xargs cat 2>/dev/null | wc -l)

if [ "$total" -gt "$LIMIT" ]; then
  echo "FAIL: Total Shell LOC $total exceeds $LIMIT limit"
  exit 1
else
  echo "✅ Total Shell LOC: $total / $LIMIT"
fi