#!/bin/bash
# Block destructive system-level commands and quality gate bypasses
INPUT=$(cat)
CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if [ -z "$CMD" ]; then
  exit 0
fi

PATTERNS=(
  "rm\s+-rf\s+(/|~|\$HOME)"
  "rm\s+-rf\s+.*\s+(/|~)"
  "git\s+commit\s+.*--no-verify"
  "(DROP|TRUNCATE)\s+(TABLE|DATABASE)"
  "task\s+resume\s+(?!.*--label).*(-y\b|--yes\b)"
)

for pattern in "${PATTERNS[@]}"; do
  if echo "$CMD" | grep -qiE "$pattern"; then
    echo "[security] BLOCKED: destructive command pattern detected" >&2
    echo "[security] Command: $CMD" >&2
    exit 2
  fi
done

exit 0
