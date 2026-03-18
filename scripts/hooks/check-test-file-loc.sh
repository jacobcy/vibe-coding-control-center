#!/usr/bin/env bash
# Check per-file LOC ceiling for test files
# Reads limits from config/settings.yaml
#
# Limits:
#   default: 200 lines (most test files should fit)
#   max: 300 lines (special cases with justification)

set -e

get_limit() {
  PYTHONPATH=src uv run python -m vibe3.config.get \
    "$1" -c config/settings.yaml --quiet 2>/dev/null || echo "$2"
}

LIMIT_DEFAULT=$(get_limit "code_limits.v3_python.test_file_loc.default" 200)
LIMIT_MAX=$(get_limit "code_limits.v3_python.test_file_loc.max" 300)

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

for f in $(find tests/vibe3 -name "test_*.py" 2>/dev/null); do
  check_file "$f" "$LIMIT_MAX"
done

if [ "$failed" -gt 0 ]; then
  echo "FAIL: $failed test files exceed $LIMIT_MAX line limit"
  echo "Tip: Default limit is $LIMIT_DEFAULT lines. Use up to $LIMIT_MAX for special cases."
  exit 1
else
  echo "✅ All test files within limit (max: $LIMIT_MAX lines, default: $LIMIT_DEFAULT)"
fi
