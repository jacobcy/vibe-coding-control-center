#!/bin/bash
# Block destructive system-level commands and quality gate bypasses
INPUT=$(cat)
CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if [ -z "$CMD" ]; then
  exit 0
fi

PATTERNS=(
  "(^|\s|&&|;)rm\s+(-\w*[rf]\w*\s+)*(/|~|\$HOME)(\s|$)"
  "(^|\s|&&|;)rm\s+(-\w*[rf]\w*\s+)+(\.?venv|\.?node_modules|\.?virtualenv)(/|$)"
  "(^|\s|&&|;)rm\s+(-\w*[rf]\w*\s+)+.*/(\.?venv|\.?node_modules|\.?virtualenv)(/|$)"
  "(^|\s|&&|;)rm\s+(-\w*[rf]\w*\s+)+\.?env(/|$)"
  "git\s+commit\s+.*--no-verify"
  "(DROP|TRUNCATE)\s+(TABLE|DATABASE)"
)

# Block task resume -y without --label (grep -E lacks lookahead)
if echo "$CMD" | grep -qiE "task\s+resume\s+.*(-y\b|--yes\b)" && \
   ! echo "$CMD" | grep -qiE "task\s+resume\s+.*--label"; then
  echo "[security] BLOCKED: unsafe task resume without --label" >&2
  echo "[security] Command: $CMD" >&2
  exit 2
fi

for pattern in "${PATTERNS[@]}"; do
  if echo "$CMD" | grep -qiE "$pattern"; then
    echo "[security] BLOCKED: destructive command pattern detected" >&2
    echo "[security] Command: $CMD" >&2
    exit 2
  fi
done

exit 0
