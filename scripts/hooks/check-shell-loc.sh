#!/usr/bin/env bash
# Check Shell LOC ceiling (core code only)
#
# Behavior:
#   - Local hooks (pre-commit/pre-push): WARNING ONLY (exit 0)
#   - CI: Set env var ENFORCE_LOC_LIMITS=true to BLOCK on violations
#
# Uses only the Python standard library so it can run before uv sync.
#
# Code paths (defined in config/settings.yaml:code_limits.code_paths.v2_shell):
#   - lib/
#   - lib3/
#   - bin/vibe
#
# Note: scripts/ NOT included in total LOC (checked separately for single-file limits only)

set -e

result=$(python3 - <<'PY'
from pathlib import Path
import re


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


def count_loc(patterns: list[str]) -> int:
  total = 0
  for pattern in patterns:
    for path in sorted(Path(".").glob(pattern)):
      if path.is_file():
        total += sum(1 for _ in path.open())
  return total


config = parse_config("config/settings.yaml")
limit_total = int(config["code_limits.total_file_loc.v2_shell"])
total_loc = count_loc(["lib/*.sh", "lib3/*.sh", "bin/vibe"])

print(f"{total_loc} {limit_total}")
PY
)

total=$(echo "$result" | awk '{print $1}')
LIMIT=$(echo "$result" | awk '{print $2}')

if [ "$total" -gt "$LIMIT" ]; then
  echo "⚠️  WARNING: Total Shell LOC $total exceeds $LIMIT limit"
  echo "   This is a soft constraint in local development"
  echo ""
  echo "💡 Tip: Split large functions, remove dead code, use libraries"

  # In CI (ENFORCE_LOC_LIMITS=true), block on violations
  if [ "${ENFORCE_LOC_LIMITS:-false}" = "true" ]; then
    echo ""
    echo "❌ CI ENFORCEMENT: LOC limit exceeded - blocking pipeline"
    exit 1
  else
    echo ""
    echo "   Push allowed (local development)"
    exit 0
  fi
else
  echo "✅ Total Shell LOC: $total / $LIMIT"
fi
