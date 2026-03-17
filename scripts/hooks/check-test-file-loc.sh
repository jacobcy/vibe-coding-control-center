#!/usr/bin/env bash
# Check per-file LOC ceiling for test files (layer-aware)
# Reads limits from config/settings.yaml via Python config module
#
# Limits by layer:
#   tests/vibe3/services/  → code_limits.v3_python.test_file_loc.services (180)
#   tests/vibe3/clients/   → code_limits.v3_python.test_file_loc.clients  (200)
#   tests/vibe3/commands/  → code_limits.v3_python.test_file_loc.commands  (80)

set -e

get_limit() {
  PYTHONPATH=src uv run python -m vibe3.config.get \
    "$1" -c config/settings.yaml --quiet 2>/dev/null || echo "$2"
}

LIMIT_SERVICES=$(get_limit "code_limits.v3_python.test_file_loc.services" 180)
LIMIT_CLIENTS=$(get_limit  "code_limits.v3_python.test_file_loc.clients"  200)
LIMIT_COMMANDS=$(get_limit "code_limits.v3_python.test_file_loc.commands"  80)

failed=0

check_file() {
  local f="$1"
  local limit="$2"
  local lines
  lines=$(wc -l < "$f")
  if [ "$lines" -gt "$limit" ]; then
    echo "FAIL: $f has $lines lines (limit: $limit)"
    failed=$((failed + 1))
  fi
}

for f in $(find tests/vibe3/services  -name "test_*.py" 2>/dev/null); do check_file "$f" "$LIMIT_SERVICES";  done
for f in $(find tests/vibe3/clients   -name "test_*.py" 2>/dev/null); do check_file "$f" "$LIMIT_CLIENTS";   done
for f in $(find tests/vibe3/commands  -name "test_*.py" 2>/dev/null); do check_file "$f" "$LIMIT_COMMANDS";  done

if [ "$failed" -gt 0 ]; then
  echo "FAIL: $failed test files exceed layer limits"
  exit 1
else
  echo "✅ All test files within layer limits (services≤${LIMIT_SERVICES}, clients≤${LIMIT_CLIENTS}, commands≤${LIMIT_COMMANDS})"
fi
