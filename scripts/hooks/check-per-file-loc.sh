#!/usr/bin/env bash
# Check per-file LOC ceiling for source files
# Reads limits from config/settings.yaml
#
# Limits (unified for Shell and Python):
#   default: 200 lines (most files should fit)
#   max: 300 lines (special cases with justification)
#
# Exit codes:
#   0: All files within default limit
#   1: Some files exceed max limit

set -e

get_limit() {
  PYTHONPATH=src uv run python -m vibe3.config.get \
    "$1" -c config/settings.yaml --quiet 2>/dev/null || echo "$2"
}

# Get limits (unified for both Shell and Python)
LIMIT_DEFAULT=$(get_limit "code_limits.v3_python.file_loc.default" 200)
LIMIT_MAX=$(get_limit "code_limits.v3_python.file_loc.max" 300)

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

# Check Shell files
for f in lib/*.sh lib3/*.sh bin/vibe; do
  [ -f "$f" ] || continue
  check_file "$f"
done

# Check Python files
for f in $(find src/vibe3 -name "*.py" -not -name "__init__.py" 2>/dev/null); do
  [ -f "$f" ] || continue
  check_file "$f"
done

# Report results
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Source file LOC check results:"
echo "  - Default limit: $LIMIT_DEFAULT lines"
echo "  - Max limit: $LIMIT_MAX lines"
echo "  - Warnings: $warnings files (default → max)"
echo "  - Errors: $errors files (exceed max)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$errors" -gt 0 ]; then
  echo ""
  echo "💡 Tip: Split large files into smaller, focused modules"
  echo "   - Extract utilities to separate files"
  echo "   - Use composition over inheritance"
  echo "   - Follow Single Responsibility Principle"
  exit 1
elif [ "$warnings" -gt 0 ]; then
  echo ""
  echo "💡 Tip: Consider refactoring files exceeding default limit"
  echo "   (Warnings are allowed, but keep below max limit)"
else
  echo "✅ All source files within default limit ($LIMIT_DEFAULT lines)"
fi
