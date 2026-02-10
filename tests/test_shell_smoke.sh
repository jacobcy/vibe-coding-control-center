#!/usr/bin/env zsh
# tests/test_shell_smoke.sh
# 用途: 确保交互/非交互下 utils.sh 的严格模式设置正确

SCRIPT_DIR="$(cd "$(dirname "${(%):-%x}")" && pwd)"
ROOT_DIR="$SCRIPT_DIR/.."

log() { echo "$@"; }

# 1) 交互 shell 不应启用 nounset，避免影响 oh-my-zsh 等插件
TMP_ZDOTDIR="$(mktemp -d)"
cat > "$TMP_ZDOTDIR/.zshrc" <<ZRC
source "$ROOT_DIR/lib/utils.sh"
# Source twice to ensure idempotency (no readonly errors)
source "$ROOT_DIR/lib/utils.sh"
if [[ \$options[nounset] == on ]]; then
  echo "nounset should be off in interactive shell"
  exit 1
fi
ZRC

if ! ZDOTDIR="$TMP_ZDOTDIR" zsh -ic 'exit 0' >/dev/null 2>&1; then
  log "✗ Interactive shell smoke test failed"
  rm -rf "$TMP_ZDOTDIR"
  exit 1
fi

rm -rf "$TMP_ZDOTDIR"

# 2) 非交互 shell 应启用 nounset（除非显式关闭）
if ! zsh -c "source '$ROOT_DIR/lib/utils.sh'; [[ \$options[nounset] == on ]]" >/dev/null 2>&1; then
  log "✗ Non-interactive shell should enable nounset by default"
  exit 1
fi

log "✓ Shell smoke tests passed"
