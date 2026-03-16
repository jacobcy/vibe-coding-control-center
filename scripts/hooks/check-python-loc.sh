#!/usr/bin/env bash
# Check Python LOC ceiling (scripts/python ≤ 3000)
# Used by pre-commit hooks

set -e

total=$(find scripts/python -name "*.py" | xargs cat | wc -l)

if [ "$total" -gt 3000 ]; then
  echo "FAIL: Total Python LOC $total exceeds 3000 limit"
  exit 1
else
  echo "✅ Total Python LOC: $total / 3000"
fi