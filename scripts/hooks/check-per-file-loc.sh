#!/usr/bin/env bash
# Check per-file LOC ceiling (≤ 300 lines each)
# Used by pre-commit hooks

set -e

failed=0

# Check Shell files
for f in lib/*.sh lib3/*.sh bin/vibe; do
  [ -f "$f" ] || continue
  lines=$(wc -l < "$f")
  if [ "$lines" -gt 300 ]; then
    echo "FAIL: $f has $lines lines (limit: 300)"
    failed=$((failed + 1))
  fi
done

# Check Python files
for f in $(find src/vibe3 -name "*.py" 2>/dev/null); do
  [ -f "$f" ] || continue
  lines=$(wc -l < "$f")
  if [ "$lines" -gt 300 ]; then
    echo "FAIL: $f has $lines lines (limit: 300)"
    failed=$((failed + 1))
  fi
done

if [ "$failed" -gt 0 ]; then
  echo "FAIL: $failed files exceed the 300-line limit"
  exit 1
else
  echo "✅ All files within 300-line limit"
fi