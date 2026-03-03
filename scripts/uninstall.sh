#!/usr/bin/env zsh
# Vibe Coding Control Center - Uninstaller
# Removes global installation and shell integration.

set -e

INSTALL_DIR="$HOME/.vibe"
SOURCE_ROOT="$(cd "$(dirname "${(%):-%x}")/.." && pwd)"
[[ -f "$SOURCE_ROOT/lib/utils.sh" ]] && source "$SOURCE_ROOT/lib/utils.sh" || { echo "error: missing lib/utils.sh"; exit 1; }

# --- Help ---
_usage() {
    echo "${BOLD}Vibe Coding Control Center - Uninstaller${NC}"
    echo ""
    echo "此脚本负责完全移除 Vibe 的全局分发环境："
    echo "  1. 彻底清理环境：删除 ${CYAN}~/.vibe${NC} 目录下的所有文件 (包括 API 密钥)"
    echo "  2. 撤销配置注入：移除 ${CYAN}.zshrc/.bashrc${NC} 中的加载器条目"
    echo ""
    echo "Usage: ${CYAN}scripts/uninstall.sh${NC} [options]"
    echo ""
    echo "Options:"
    echo "  -h, --help    显示此帮助信息"
    echo ""
    exit 0
}

for arg in "$@"; do
    case "$arg" in
        -h|--help) _usage ;;
    esac
done

_get_shell_rc() {
    case "$SHELL" in
        */zsh) echo "$HOME/.zshrc" ;;
        */bash) echo "$HOME/.bashrc" ;;
        *) echo "$HOME/.zshrc" ;;
    esac
}

log_step "Uninstalling Vibe Center"

# 1. Remove Shell Integration
RC_FILE="$(_get_shell_rc)"
if [[ -f "$RC_FILE" ]]; then
    log_info "Removing entries from $RC_FILE..."
    # Remove markers and the source line
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' '/# Vibe Coding Control Center/d' "$RC_FILE" 2>/dev/null || true
        sed -i '' '/source .*\/loader.sh/d' "$RC_FILE" 2>/dev/null || true
    else
        sed -i '/# Vibe Coding Control Center/d' "$RC_FILE" 2>/dev/null || true
        sed -i '/source .*\/loader.sh/d' "$RC_FILE" 2>/dev/null || true
    fi
    log_success "Cleaned $RC_FILE"
fi

# 2. Remove Installation Directory
if [[ -d "$INSTALL_DIR" ]]; then
    confirm_action "Delete $INSTALL_DIR and all its contents (including keys.env)?" || { log_info "Aborted."; exit 0; }
    rm -rf "$INSTALL_DIR"
    log_success "Removed $INSTALL_DIR"
else
    log_info "$INSTALL_DIR not found, skipping."
fi

log_success "Uninstallation complete!"
echo "💡 Please restart your terminal or run: source $RC_FILE"
echo "----------------------------------------"
