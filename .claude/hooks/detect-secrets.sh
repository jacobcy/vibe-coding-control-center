#!/bin/bash
# Detect hardcoded secrets in file writes/edits
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
NEW_TEXT=$(echo "$INPUT" | jq -r '.tool_input.new_string // .tool_input.content // empty')

if [ -z "$NEW_TEXT" ]; then
  exit 0
fi

# Skip test files and example files
if [[ "$FILE" == *.test.* ]] || [[ "$FILE" == *.spec.* ]] || [[ "$FILE" == *.example* ]]; then
  exit 0
fi

# Match patterns like API_KEY="abcdef1234567890", PASSWORD='xxx', SECRET=xxx (16+ chars)
if echo "$NEW_TEXT" | grep -qiE '(API_KEY|SECRET|TOKEN|PASSWORD|PRIVATE_KEY|ACCESS_KEY)\s*[=:]\s*["\x27]?[A-Za-z0-9_\-]{16,}'; then
  echo "[security] WARNING: possible hardcoded secret in $FILE" >&2
  echo "[security] Use environment variables instead" >&2
  # Warn only (exit 0) - don't block, let user decide
fi

exit 0
