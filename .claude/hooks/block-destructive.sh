#!/bin/bash
# Block destructive commands: rm -rf /, rm -rf ~, DROP TABLE, force push, etc.
INPUT=$(cat)
CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if [ -z "$CMD" ]; then
  exit 0
fi

PATTERNS=(
  "rm\s+-rf\s+(/|~|\$HOME)"
  "rm\s+-rf\s+.*\s+(/|~)"
  "git\s+push\s+.*(-f\s*|--force)"
  "(DROP|TRUNCATE)\s+(TABLE|DATABASE)"
)

for pattern in "${PATTERNS[@]}"; do
  if echo "$CMD" | grep -qiE "$pattern"; then
    echo "[security] BLOCKED: destructive command pattern detected" >&2
    echo "[security] Command: $CMD" >&2
    exit 2
  fi
done

exit 0
