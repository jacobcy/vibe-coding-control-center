#!/usr/bin/env bash
# Check per-file LOC ceiling for source files
#
# Behavior:
#   - Local hooks (pre-commit/pre-push): WARNING ONLY (exit 0)
#   - CI: Set env var ENFORCE_LOC_LIMITS=true to BLOCK on violations
#
# Reads limits from config/settings.yaml without uv
#
# Limits (unified for all file types):
#   default: 300 lines (most files should fit)
#   max: 400 lines (special cases with justification)

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

# Get limits (unified for all file types)
LIMIT_DEFAULT=$(get_limit "code_limits.single_file_loc.default" 300)
LIMIT_MAX=$(get_limit "code_limits.single_file_loc.max" 400)

# Files to ignore (temporarily exceed limits)
# Loaded from config/settings.yaml:code_limits.single_file_loc.exceptions
IGNORE_FILES=(
  "src/vibe3/commands/run.py"  # TODO: Extract skill execution to run_skill.py
  "src/vibe3/commands/flow.py"  # TODO: Extract GitHub Project auto-link logic
  "src/vibe3/commands/review.py"  # TODO: Extract session management
  "src/vibe3/clients/sqlite_client.py"  # TODO: Extract issue link queries to sqlite_issue_queries.py
  "src/vibe3/services/check_service.py"  # Core validation service (424 lines): _check_branch is a single-responsibility method; further splitting would break verification logic integrity
  "src/vibe3/orchestra/services/state_label_dispatch.py"  # Orchestra dispatch core (462 lines): already extracted no_progress_policy.py; remaining code is state machine core that should not be fragmented
  "tests/vibe3/orchestra/test_state_label_dispatch.py"  # Comprehensive test suite for StateLabelDispatchService (498 lines): tests share fixtures and test highly related scenarios; splitting would increase maintenance cost
  "tests/vibe3/commands/test_run_manager_issue.py"  # Test suite for manager-issue mode (479 lines): single test class with shared fixtures; splitting would break test suite integrity
  "scripts/tsu.sh"  # External script, not subject to LOC limits
  "src/vibe3/manager/worktree_manager.py"  # Worktree lifecycle management (职责内聚，共享私有方法)
  "src/vibe3/agents/backends/codeagent.py"  # Codeagent execution backend (sync/async共享基础设施)
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
