#!/usr/bin/env bash

set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "usage: $0 <skill-file>" >&2
  exit 2
fi

skill_file="$1"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../../.." && pwd)"

if [ ! -f "$skill_file" ]; then
  echo "missing skill file: $skill_file" >&2
  exit 2
fi

mapfile -t vibe_commands < <(grep -oE '`bin/vibe [^`]+`' "$skill_file" | sed 's/^`//; s/`$//' || true)

if [ "${#vibe_commands[@]}" -eq 0 ]; then
  echo "No findings: $skill_file"
  exit 0
fi

findings=0

for cmd in "${vibe_commands[@]}"; do
  subcommand="$(printf '%s\n' "$cmd" | awk '{print $2}')"

  if ! (cd "$repo_root" && ./bin/vibe "$subcommand" --help >/dev/null 2>&1); then
    echo "Capability Gap: $skill_file -> $cmd"
    findings=1
  fi
done

if [ "$findings" -eq 0 ]; then
  echo "No findings: $skill_file"
fi
