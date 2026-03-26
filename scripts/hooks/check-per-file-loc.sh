#!/usr/bin/env bash
# Check per-file LOC ceiling for source files
#
# Behavior:
#   - Local hooks (pre-commit/pre-push): WARNING ONLY (exit 0)
#   - CI: Set env var ENFORCE_LOC_LIMITS=true to BLOCK on violations
#
# Reads limits from config/settings.yaml
#
# Limits (unified for Shell and Python):
#   default: 200 lines (most files should fit)
#   max: 300 lines (special cases with justification)
#
# Code paths (defined in config/settings.yaml:code_limits.code_paths):
#   Shell: lib/, lib3/, bin/vibe
#   Python: src/vibe3/
#
# Scripts paths (defined in config/settings.yaml:code_limits.scripts_paths):
#   Shell: scripts/ (*.sh files)
#   Python: scripts/ (*.py files)
#
# Note: scripts/ are checked for single-file limits but NOT counted in total LOC

set -e

get_limit() {
  PYTHONPATH=src uv run python -m vibe3.config.get \
    "$1" -c config/settings.yaml --quiet 2>/dev/null || echo "$2"
}

# Get limits (unified for all file types)
LIMIT_DEFAULT=$(get_limit "code_limits.single_file_loc.default" 200)
LIMIT_MAX=$(get_limit "code_limits.single_file_loc.max" 300)

# Files to ignore (temporarily exceed limits)
IGNORE_FILES=(
  "src/vibe3/commands/run.py"  # TODO: Extract skill execution to run_skill.py
  "src/vibe3/commands/flow.py"  # TODO: Extract GitHub Project auto-link logic
  "src/vibe3/commands/review.py"  # TODO: Extract session management
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

# Check Shell files (paths defined in config: code_limits.code_paths.v2_shell)
for f in lib/*.sh lib3/*.sh bin/vibe; do
  [ -f "$f" ] || continue
  check_file "$f"
done

# Check scripts/*.sh files
for f in $(find scripts/ -name "*.sh" 2>/dev/null); do
  [ -f "$f" ] || continue
  check_file "$f"
done

# Check Python files (paths defined in config: code_limits.code_paths.v3_python)
for f in $(find src/vibe3 -name "*.py" -not -name "__init__.py" 2>/dev/null); do
  [ -f "$f" ] || continue
  check_file "$f"
done

# Check scripts/*.py files
for f in $(find scripts/ -name "*.py" 2>/dev/null); do
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
  echo "⚠️  WARNING: $errors files exceed max limit ($LIMIT_MAX lines)"
  echo "   This is a soft constraint in local development"
  echo ""
  echo "💡 Tip: Split large files into smaller, focused modules"
  echo "   - Extract utilities to separate files"
  echo "   - Use composition over inheritance"
  echo "   - Follow Single Responsibility Principle"

  # In CI (ENFORCE_LOC_LIMITS=true), block on violations
  if [ "${ENFORCE_LOC_LIMITS:-false}" = "true" ]; then
    echo ""
    echo "❌ CI ENFORCEMENT: Files exceed max LOC limit - blocking pipeline"
    exit 1
  else
    echo ""
    echo "   Push allowed (local development)"
    exit 0
  fi
elif [ "$warnings" -gt 0 ]; then
  echo ""
  echo "⚠️  WARNING: $warnings files exceed default limit ($LIMIT_DEFAULT lines)"
  echo "   This is a soft constraint in local development"
  echo ""
  echo "💡 Tip: Consider refactoring files exceeding default limit"
  echo "   (Warnings are allowed, but keep below max limit)"
else
  echo "✅ All source files within default limit ($LIMIT_DEFAULT lines)"
fi
