#!/usr/bin/env bash
# Check Shell LOC ceiling (lib/ + bin/ + lib3/ ≤ 7000)
# Used by pre-commit hooks

set -e

total=$(find lib/ bin/ lib3/ -name "*.sh" -o -name "vibe" 2>/dev/null | xargs cat 2>/dev/null | wc -l)

if [ "$total" -gt 7000 ]; then
  echo "FAIL: Total Shell LOC $total exceeds 7000 limit"
  exit 1
else
  echo "✅ Total Shell LOC: $total / 7000"
fi