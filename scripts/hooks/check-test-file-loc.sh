#!/usr/bin/env bash
# Check per-file LOC ceiling for test files
# Reads limits from config/settings.yaml
#
# Limits:
#   default: 200 lines (most test files should fit)
#   max: 300 lines (special cases with justification)
#
# Exit codes:
#   0: All files within default limit
#   1: Some files exceed max limit (or warnings with strict mode)

set -e

get_limit() {
  PYTHONPATH=src uv run python -m vibe3.config.get \
    "$1" -c config/settings.yaml --quiet 2>/dev/null || echo "$2"
}

LIMIT_DEFAULT=$(get_limit "code_limits.v3_python.test_file_loc.default" 200)
LIMIT_MAX=$(get_limit "code_limits.v3_python.test_file_loc.max" 300)

warnings=0
errors=0

check_file() {
  local f="$1"
  local lines
  lines=$(wc -l < "$f")

  # Check max limit (error)
  if [ "$lines" -gt "$LIMIT_MAX" ]; then
    echo "❌ ERROR: $f has $lines lines (max: $LIMIT_MAX)"
    errors=$((errors + 1))
  # Check default limit (warning)
  elif [ "$lines" -gt "$LIMIT_DEFAULT" ]; then
    echo "⚠️  WARNING: $f has $lines lines (default: $LIMIT_DEFAULT, max: $LIMIT_MAX)"
    warnings=$((warnings + 1))
  fi
}

for f in $(find tests/vibe3 -name "test_*.py" 2>/dev/null); do
  check_file "$f"
done

# Report results
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test file LOC check results:"
echo "  - Default limit: $LIMIT_DEFAULT lines"
echo "  - Max limit: $LIMIT_MAX lines"
echo "  - Warnings: $warnings files (default → max)"
echo "  - Errors: $errors files (exceed max)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$errors" -gt 0 ]; then
  echo ""
  echo "💡 Tip: Split large test files into smaller, focused modules"
  exit 1
elif [ "$warnings" -gt 0 ]; then
  echo ""
  echo "💡 Tip: Consider refactoring files exceeding default limit"
  echo "   (Warnings are allowed, but keep below max limit)"
else
  echo "✅ All test files within default limit ($LIMIT_DEFAULT lines)"
fi
