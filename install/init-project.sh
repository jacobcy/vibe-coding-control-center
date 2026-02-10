#!/usr/bin/env zsh
# init-project.sh
# Entry point for project initialization

if [ -z "${ZSH_VERSION:-}" ]; then
    if command -v zsh >/dev/null 2>&1; then
        exec zsh -l "$0" "$@"
    fi
    echo "zsh not found. Please run ./scripts/install.sh to install zsh." >&2
    exit 1
fi

set -e

# Ensure core utilities are on PATH (non-login shells may have a minimal PATH)
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${(%):-%x}")" && pwd)"

source "$SCRIPT_DIR/../lib/utils.sh"
source "$SCRIPT_DIR/../lib/config.sh"
source "$SCRIPT_DIR/../lib/i18n.sh"
source "$SCRIPT_DIR/../lib/agents.sh"
source "$SCRIPT_DIR/../lib/init_project.sh"

load_user_config

log_step "AI 项目初始化脚本 (Cursor & Claude)"

# Re-ensure PATH after loading user config
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

mode="ai"
if [[ "$1" == "--local" ]]; then
    mode="local"
    shift
elif [[ "$1" == "--ai" ]]; then
    mode="ai"
    shift
fi

preset_dir="${1:-}"

vibe_collect_init_answers "$preset_dir" || exit 1
vibe_init_project "$mode"
