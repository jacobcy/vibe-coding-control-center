#!/usr/bin/env bash
# Check per-file LOC ceiling for source files
#
# Behavior:
#   - Local hooks (pre-commit/pre-push): WARNING ONLY (exit 0)
#   - CI: Set env var ENFORCE_LOC_LIMITS=true to BLOCK on violations
#
# Reads limits from config/v3/loc_limits.yaml without uv
#
# Limits (unified for all file types):
#   default: 300 lines (most files should fit)
#   max: 400 lines (special cases with justification)

#
# Code paths (defined in config/v3/loc_limits.yaml:code_limits.code_paths):
#   Shell: lib/, lib3/, bin/vibe
#   Python: src/vibe3/
#
# Scripts paths (defined in config/loc_limits.yaml:code_limits.scripts_paths):
#   Shell: scripts/ (*.sh files)
#   Python: scripts/ (*.py files)
#
# Note: scripts/ are checked for single-file limits but NOT counted in total LOC

set -e

result=$(python3 - <<'PY'
from pathlib import Path
import sys

sys.path.insert(0, str(Path("scripts/hooks").resolve()))

from loc_settings import find_exception, iter_files, load_loc_settings


config = load_loc_settings()
warnings = 0
errors = 0

files = {
    path.as_posix(): path
    for path in (
        iter_files(config.code_paths_v2_shell, suffixes=(".sh",))
        + iter_files(config.code_paths_v3_python, suffixes=(".py",))
        + iter_files(config.scripts_paths_v2_shell, suffixes=(".sh",))
        + iter_files(config.scripts_paths_v3_python, suffixes=(".py",))
    )
}
for file_path in [files[key] for key in sorted(files)]:
    if file_path.name == "__init__.py":
        continue

    rel_path = file_path.as_posix()
    lines = sum(1 for _ in file_path.open())
    exception = find_exception(config.exceptions, rel_path)
    limit = exception.limit if exception else config.single_file_max

    if lines > limit:
        label = f"custom: {limit}" if exception else f"max: {config.single_file_max}"
        print(f"❌ ERROR: {rel_path} has {lines} lines ({label})")
        errors += 1
    elif exception is None and lines > config.single_file_default:
        print(
            f"⚠️  WARNING: {rel_path} has {lines} lines "
            f"(default: {config.single_file_default}, max: {config.single_file_max})"
        )
        warnings += 1

print()
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("Source file LOC check results:")
print(f"  - Default limit: {config.single_file_default} lines")
print(f"  - Max limit: {config.single_file_max} lines")
print(f"  - Warnings: {warnings} files (default → max)")
print(f"  - Errors: {errors} files (exceed max)")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print(f"COUNTS {warnings} {errors} {config.single_file_default} {config.single_file_max}")
PY
)

echo "$result" | sed '$d'

COUNTS_LINE=$(echo "$result" | tail -n 1)
warnings=$(echo "$COUNTS_LINE" | awk '{print $2}')
errors=$(echo "$COUNTS_LINE" | awk '{print $3}')
LIMIT_DEFAULT=$(echo "$COUNTS_LINE" | awk '{print $4}')
LIMIT_MAX=$(echo "$COUNTS_LINE" | awk '{print $5}')

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
