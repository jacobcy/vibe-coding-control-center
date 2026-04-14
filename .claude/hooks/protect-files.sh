#!/bin/bash
# Protect sensitive files from being written/edited
# Allow template files (*.template.*, *.example*) to be edited
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [ -z "$FILE" ]; then
  exit 0
fi

# Allow template and example files
if [[ "$FILE" == *.template.* ]] || [[ "$FILE" == *.example* ]] || [[ "$FILE" == *template* ]]; then
  exit 0
fi

PROTECTED=(".env" ".env.local" ".env.production" ".env.staging" "secrets/" "credentials" ".ssh/" "id_rsa" "id_ed25519")

for pattern in "${PROTECTED[@]}"; do
  if [[ "$FILE" == *"$pattern"* ]]; then
    echo "[security] BLOCKED: protected file '$FILE' matches '$pattern'" >&2
    echo "[security] Use environment variables or secret managers instead" >&2
    exit 2
  fi
done

exit 0