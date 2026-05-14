#!/usr/bin/env bash
set -euo pipefail

# Test that all script paths in skill.md exist

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
SKILL_FILE="${PROJECT_ROOT}/skills/vibe-review-pr/skill.md"

echo "Testing script paths in ${SKILL_FILE}"

# Extract all script references
extracted_paths=$(grep -oE '(skills/vibe-review-pr/scripts/[a-z-]+\.sh|\.claude/skills/vibe-review-pr/scripts/[a-z-]+\.sh)' "$SKILL_FILE" | sort -u)

echo "Found paths:"
echo "$extracted_paths"
echo

# Check each path
errors=0
while IFS= read -r path; do
  # Skip empty lines
  [[ -z "$path" ]] && continue

  # Convert to absolute path
  abs_path="${PROJECT_ROOT}/${path}"

  if [[ ! -f "$abs_path" ]]; then
    echo "ERROR: Path does not exist: $path"
    ((errors++))
  else
    echo "OK: $path"
  fi
done <<< "$extracted_paths"

if [[ $errors -gt 0 ]]; then
  echo
  echo "FAILED: $errors path(s) do not exist"
  exit 1
fi

echo
echo "SUCCESS: All paths exist"
