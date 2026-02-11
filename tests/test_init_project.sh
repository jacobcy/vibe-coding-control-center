#!/usr/bin/env zsh
# Smoke test for project initialization (local mode)

set -e

SCRIPT_DIR="$(cd "$(dirname "${(%):-%x}")" && pwd)"
ROOT_DIR="$SCRIPT_DIR/.."

BIN="$ROOT_DIR/bin/vibe-init"

if [[ ! -x "$BIN" ]]; then
  echo "vibe-init not executable: $BIN" >&2
  exit 1
fi

TMP_DIR="$(mktemp -d)"
TARGET="vibe-init-test"

# Run local init with defaults (non-interactive uses defaults)
(
  cd "$TMP_DIR" || exit 1
  "$BIN" --local "$TARGET" < /dev/null >/dev/null 2>&1
) || {
  echo "vibe init --local failed" >&2
  exit 1
}

# Cleanup on exit
trap 'rm -rf "$TMP_DIR"' EXIT

required_files=(
  "$TMP_DIR/$TARGET/SOUL.md"
  "$TMP_DIR/$TARGET/RULES.md"
  "$TMP_DIR/$TARGET/AGENT.md"
  "$TMP_DIR/$TARGET/TASK.md"
  "$TMP_DIR/$TARGET/CLAUDE.md"
  "$TMP_DIR/$TARGET/.cursor/rules/tech-stack.mdc"
  "$TMP_DIR/$TARGET/.git"
)

for f in "${required_files[@]}"; do
  if [[ ! -e "$f" ]]; then
    echo "missing: $f" >&2
    exit 1
  fi
 done

if ! rg -n "Linked Docs" "$TMP_DIR/$TARGET/CLAUDE.md" >/dev/null 2>&1; then
  echo "CLAUDE.md missing Linked Docs section" >&2
  exit 1
fi

echo "✓ init project smoke test passed"
