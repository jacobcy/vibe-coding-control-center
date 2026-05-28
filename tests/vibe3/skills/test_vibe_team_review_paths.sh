#!/usr/bin/env bash
set -euo pipefail

# Test that all script paths in vibe-team-review skill markdown files exist

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
SKILL_DIR="${PROJECT_ROOT}/skills/vibe-team-review"

echo "Testing script paths in ${SKILL_DIR}"
echo

# Find all markdown files in the skill directory
errors=0
total_files=0

md_files=$(/usr/bin/find "$SKILL_DIR" -name "*.md" -type f | sort)

for md_file in $md_files; do
  total_files=$((total_files + 1))
  rel_file="${md_file#${PROJECT_ROOT}/}"
  echo "Checking: $rel_file"

  # Extract all script references from this file
  extracted_paths=$(grep -oE '(skills/vibe-team-review/scripts/[a-z-]+\.sh|\.claude/skills/vibe-team-review/scripts/[a-z-]+\.sh)' "$md_file" 2>/dev/null | sort -u || true)

  # Check each path found in this file
  file_errors=0
  if [[ -n "$extracted_paths" ]]; then
    while IFS= read -r path; do
      # Skip empty lines
      [[ -z "$path" ]] && continue

      # Check for old incorrect path pattern
      if [[ "$path" =~ ^\.claude/skills/ ]]; then
        echo "  ERROR: Found old incorrect path pattern: $path"
        file_errors=$((file_errors + 1))
        continue
      fi

      # Convert to absolute path
      abs_path="${PROJECT_ROOT}/${path}"

      if [[ ! -f "$abs_path" ]]; then
        echo "  ERROR: Path does not exist: $path"
        file_errors=$((file_errors + 1))
      else
        echo "  OK: $path"
      fi
    done <<< "$extracted_paths"
  fi

  if [[ $file_errors -gt 0 ]]; then
    errors=$((errors + file_errors))
    echo "  FAILED: $file_errors error(s) in $rel_file"
  else
    echo "  PASSED: $rel_file"
  fi
  echo
done

echo "==========================="
echo "Summary:"
echo "  Total files checked: $total_files"
echo "  Total errors: $errors"
echo "==========================="

if [[ $errors -gt 0 ]]; then
  echo "FAILED: $errors path error(s) found"
  exit 1
fi

echo "SUCCESS: All paths in all markdown files are valid"
