#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$SKILL_DIR/../.." && pwd)"

target="${1:-}"

if [[ -z "$target" ]]; then
  echo "Usage: $0 <path-to-skill-md>" >&2
  exit 1
fi

if [[ ! -f "$target" ]]; then
  echo "Missing skill file: $target" >&2
  exit 1
fi

tmp_report="$(mktemp)"
trap 'rm -f "$tmp_report"' EXIT

record() {
  local bucket="$1"
  local message="$2"
  printf '%s|%s\n' "$bucket" "$message" >>"$tmp_report"
}

skill_text="$(cat "$target")"

needs_reference() {
  local pattern="$1"
  [[ "$skill_text" =~ $pattern ]]
}

check_reference() {
  local rel_path="$1"
  if [[ "$skill_text" != *"$rel_path"* ]]; then
    record "Missing Reference" "$rel_path"
  fi
}

file_timestamp() {
  local path="$1"
  local git_ts=""
  git_ts="$(git -C "$REPO_ROOT" log -1 --format=%ct -- "$path" 2>/dev/null || true)"
  if [[ -n "$git_ts" ]]; then
    printf '%s\n' "$git_ts"
  else
    stat -f '%m' "$path"
  fi
}

strip_ticks() {
  sed 's/^`//; s/`$//'
}

command_exists() {
  local domain="$1"
  "$REPO_ROOT/bin/vibe" "$domain" help >/dev/null 2>&1
}

subcommand_exists() {
  local domain="$1"
  local subcmd="$2"
  local help_output=""
  help_output="$("$REPO_ROOT/bin/vibe" "$domain" help 2>/dev/null || true)"
  [[ "$help_output" == *"$subcmd"* ]]
}

check_reference "docs/standards/glossary.md"
check_reference "docs/standards/action-verbs.md"

if needs_reference 'bin/vibe[[:space:]]+'; then
  check_reference "docs/standards/command-standard.md"
  check_reference "docs/standards/shell-capability-design.md"
fi

if needs_reference '(^|[^[:alpha:]])(flow|branch|worktree|pr)([^[:alpha:]]|$)'; then
  check_reference "docs/standards/git-workflow-standard.md"
  check_reference "docs/standards/worktree-lifecycle-standard.md"
fi

skill_ts="$(file_timestamp "$target")"

while IFS= read -r ref_path; do
  [[ -z "$ref_path" ]] && continue
  abs_ref="$REPO_ROOT/$ref_path"
  if [[ -f "$abs_ref" ]]; then
    ref_ts="$(file_timestamp "$abs_ref")"
    if [[ "$ref_ts" -gt "$skill_ts" ]]; then
      record "Drift Warning" "$ref_path is newer than $(realpath --relative-to="$REPO_ROOT" "$target" 2>/dev/null || python3 - <<'PY' "$REPO_ROOT" "$target"
import os, sys
print(os.path.relpath(sys.argv[2], sys.argv[1]))
PY
)"
    fi
  fi
done < <(printf '%s\n' \
  "docs/standards/glossary.md" \
  "docs/standards/action-verbs.md" \
  "docs/standards/command-standard.md" \
  "docs/standards/shell-capability-design.md" \
  "docs/standards/git-workflow-standard.md" \
  "docs/standards/worktree-lifecycle-standard.md")

while IFS= read -r raw_cmd; do
  [[ -z "$raw_cmd" ]] && continue
  cmd="$(printf '%s\n' "$raw_cmd" | strip_ticks)"
  read -r -a parts <<<"$cmd"
  [[ "${#parts[@]}" -lt 2 ]] && continue
  [[ "${parts[0]}" == "bin/vibe" ]] || continue

  domain="${parts[1]}"
  if ! command_exists "$domain"; then
    record "Capability Gap" "$cmd"
    continue
  fi

  if [[ "${#parts[@]}" -ge 3 ]]; then
    subcmd="${parts[2]}"
    case "$subcmd" in
      --help|-h|help|--json|check|json)
        ;;
      *)
        if ! subcommand_exists "$domain" "$subcmd"; then
          record "Capability Gap" "$cmd"
        fi
        ;;
    esac
  fi
done < <(python3 - <<'PY' "$target"
import re
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text()
seen = []
for match in re.findall(r'`([^`]*bin/vibe[^`]*)`', text):
    if match not in seen:
        seen.append(match)
for item in seen:
    print(item)
PY
)

if [[ ! -s "$tmp_report" ]]; then
  printf 'No findings: %s\n' "$(realpath --relative-to="$REPO_ROOT" "$target" 2>/dev/null || python3 - <<'PY' "$REPO_ROOT" "$target"
import os, sys
print(os.path.relpath(sys.argv[2], sys.argv[1]))
PY
)"
  exit 0
fi

while IFS='|' read -r bucket message; do
  printf '%s: %s\n' "$bucket" "$message"
done <"$tmp_report"
