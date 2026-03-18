#!/usr/bin/env bash
# Check per-file LOC ceiling
# Reads limit from config/settings.yaml via Python config module

set -e

# Read limit from config
LIMIT=$(PYTHONPATH=src uv run python -m vibe3.config.get \
    code_limits.v3_python.max_file_loc \
    -c config/settings.yaml \
    --quiet 2>/dev/null || echo 300)

failed=0

# Check Shell files
for f in lib/*.sh lib3/*.sh bin/vibe; do
  [ -f "$f" ] || continue
  lines=$(wc -l < "$f")
  if [ "$lines" -gt "$LIMIT" ]; then
    echo "FAIL: $f has $lines lines (limit: $LIMIT)"
    failed=$((failed + 1))
  fi
done

# Check Python files
for f in $(find src/vibe3 -name "*.py" 2>/dev/null); do
  [ -f "$f" ] || continue
  lines=$(wc -l < "$f")
  if [ "$lines" -gt "$LIMIT" ]; then
    echo "FAIL: $f has $lines lines (limit: $LIMIT)"
    failed=$((failed + 1))
  fi
done

if [ "$failed" -gt 0 ]; then
  echo "FAIL: $failed files exceed the $LIMIT-line limit"
  exit 1
else
  echo "✅ All files within $LIMIT-line limit"
fi
