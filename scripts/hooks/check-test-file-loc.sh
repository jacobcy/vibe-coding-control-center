#!/usr/bin/env bash
# Check per-file LOC ceiling for test files
# Reads limits from config/settings.yaml without uv
#
# Limits:
#   default: 300 lines (most test files should fit)
#   max: 400 lines (special cases with justification)
#
# Test paths (defined in config/settings.yaml:code_limits.test_paths):
#   Python: tests/vibe3/
#
# Exit codes:
#   0: All files within default limit
#   1: Some files exceed max limit (or warnings with strict mode)

set -e

get_limit() {
  python3 - "$1" "${2:-}" <<'PY'
import re
import sys
from pathlib import Path


def parse_config(path: str) -> dict[str, str]:
  values: dict[str, str] = {}
  stack: list[tuple[int, str]] = []

  for raw_line in Path(path).read_text().splitlines():
    stripped = raw_line.strip()
    if not stripped or stripped.startswith("#"):
      continue

    indent = len(raw_line) - len(raw_line.lstrip(" "))
    while stack and stack[-1][0] >= indent:
      stack.pop()

    match = re.match(r"([A-Za-z0-9_]+):(?:\s*(.*))?$", stripped)
    if not match:
      continue

    key, value = match.groups()
    if not value:
      stack.append((indent, key))
      continue

    path_key = ".".join([item[1] for item in stack] + [key])
    values[path_key] = value.split("#", 1)[0].strip().strip('"').strip("'")

  return values


config = parse_config("config/settings.yaml")
print(config.get(sys.argv[1], sys.argv[2]))
PY
}

# Get limits (unified for all test files)
LIMIT_DEFAULT=$(get_limit "code_limits.single_file_loc.default" 300)
LIMIT_MAX=$(get_limit "code_limits.single_file_loc.max" 400)

# Test files to ignore (comprehensive test suites that should not be fragmented)
IGNORE_FILES=(
  "tests/vibe3/orchestra/test_state_label_dispatch.py"  # Comprehensive test suite for StateLabelDispatchService (498 lines): tests share fixtures and test highly related scenarios; splitting would increase maintenance cost
  "tests/vibe3/commands/test_run_manager_issue.py"  # Test suite for manager-issue mode (479 lines): single test class with shared fixtures; splitting would break test suite integrity
)

warnings=0
errors=0

should_ignore() {
  local f="$1"
  for ignore in "${IGNORE_FILES[@]}"; do
    if [ "$f" = "$ignore" ]; then
      return 0
    fi
  done
  return 1
}

check_file() {
  local f="$1"

  # Skip ignored files
  if should_ignore "$f"; then
    return
  fi

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

# Check Python test files (paths defined in config: code_limits.test_paths.v3_python)
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
