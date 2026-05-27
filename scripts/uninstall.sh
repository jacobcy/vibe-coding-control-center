#!/usr/bin/env zsh
# Vibe Coding Control Center - Uninstaller
# Removes global installation and shell integration.

set -euo pipefail

INSTALL_DIR="$HOME/.vibe"
SOURCE_ROOT="$(cd "$(dirname "${(%):-%x}")/.." && pwd)"
[[ -f "$SOURCE_ROOT/lib/utils.sh" ]] && source "$SOURCE_ROOT/lib/utils.sh" || { echo "error: missing lib/utils.sh"; exit 1; }

# Directories synced during install (must match install.sh line 147)
SYNC_DIRS="bin lib lib3 config scripts alias src skills"

# --- Help ---
_usage() {
    echo "${BOLD}Vibe Coding Control Center - Uninstaller${NC}"
    echo ""
    echo "此脚本负责完全移除 Vibe 的全局分发环境："
    echo "  1. 彻底清理环境：删除 ${CYAN}~/.vibe${NC} 目录及所有同步组件"
    echo "     同步组件包括：bin, lib, lib3, config, scripts, alias, src, skills"
    echo "  2. 撤销配置注入：移除 ${CYAN}.zshrc/.bashrc${NC} 中的加载器条目"
    echo "  3. 可选保留用户数据（${CYAN}--keep-data${NC}）"
    echo ""
    echo "Usage: ${CYAN}scripts/uninstall.sh${NC} [options]"
    echo ""
    echo "Options:"
    echo "  -h, --help        显示此帮助信息"
    echo "  -y, --yes         跳过确认提示"
    echo "  --keep-data       保留用户数据（keys.env, skills.json）"
    echo ""
    exit 0
}

# Parse arguments
KEEP_DATA=false
SKIP_CONFIRM=false

for arg in "$@"; do
    case "$arg" in
        -h|--help) _usage ;;
        -y|--yes) SKIP_CONFIRM=true ;;
        --keep-data) KEEP_DATA=true ;;
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

# Check if installation exists
if [[ ! -d "$INSTALL_DIR" ]]; then
    log_warning "Vibe Center installation not found at $INSTALL_DIR"
    log_info "Already uninstalled or never installed."
    exit 0
fi

# --- Confirmation ---
if [[ "$SKIP_CONFIRM" != true ]]; then
    echo ""
    echo "${BOLD}⚠️  This will remove Vibe Center installation from $INSTALL_DIR${NC}"
    echo ""

    if [[ "$KEEP_DATA" == true ]]; then
        log_info "User data will be preserved:"
        echo "   - $INSTALL_DIR/config/keys.env"
        echo "   - $INSTALL_DIR/skills.json"
    else
        log_warning "All user data will be removed, including:"
        echo "   - Configuration files (config/)"
        echo "   - Policies and assets (assets/)"
        echo "   - User keys (config/keys.env)"
        echo "   - Skills config (skills.json)"
        echo "   - All synced directories (bin, lib, lib3, scripts, alias, src, skills)"
    fi
    echo ""

    confirm_action "Continue?" || { log_info "Aborted."; exit 0; }
fi

# --- Preserve user data if requested ---
TEMP_BACKUP=""
if [[ "$KEEP_DATA" == true ]]; then
    log_info "Preserving user data..."
    TEMP_BACKUP=$(mktemp -d)

    # Backup keys.env
    if [[ -f "$INSTALL_DIR/config/keys.env" ]]; then
        cp "$INSTALL_DIR/config/keys.env" "$TEMP_BACKUP/"
        log_success "Backed up keys.env"
    fi

    # Backup skills.json
    if [[ -f "$INSTALL_DIR/skills.json" ]]; then
        cp "$INSTALL_DIR/skills.json" "$TEMP_BACKUP/"
        log_success "Backed up skills.json"
    fi
fi

# 1. Explicitly remove synced directories
log_info "Removing synced directories..."
for dir in $SYNC_DIRS; do
    if [[ -d "$INSTALL_DIR/$dir" ]]; then
        rm -rf "$INSTALL_DIR/$dir"
        log_success "Removed $INSTALL_DIR/$dir"
    fi
done

# 2. Remove Installation Directory (safety net for any remaining files)
log_info "Removing installation directory..."
if [[ -d "$INSTALL_DIR" ]]; then
    rm -rf "$INSTALL_DIR"
    log_success "Removed $INSTALL_DIR"
fi

# 3. Restore user data if preserved
if [[ "$KEEP_DATA" == true ]] && [[ -n "$TEMP_BACKUP" ]]; then
    log_info "Restoring user data to $INSTALL_DIR..."

    mkdir -p "$INSTALL_DIR/config"

    if [[ -f "$TEMP_BACKUP/keys.env" ]]; then
        mv "$TEMP_BACKUP/keys.env" "$INSTALL_DIR/config/"
        chmod 600 "$INSTALL_DIR/config/keys.env"
        log_success "Restored keys.env"
    fi

    if [[ -f "$TEMP_BACKUP/skills.json" ]]; then
        mv "$TEMP_BACKUP/skills.json" "$INSTALL_DIR/"
        log_success "Restored skills.json"
    fi

    rm -rf "$TEMP_BACKUP"
fi

# 4. Remove Shell Integration
log_info "Cleaning shell configuration files..."

_clean_rc_file() {
    local rc_file="$1"

    if [[ ! -f "$rc_file" ]]; then
        return
    fi

    # Create backup
    cp "$rc_file" "$rc_file.vibe-backup"

    # Remove Vibe-related lines using markers as anchors
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS sed
        sed -i '' '/# Vibe Center - codeagent-wrapper PATH/,+1 d' "$rc_file" 2>/dev/null || true
        sed -i '' '/# Load Vibe keys/,+5 d' "$rc_file" 2>/dev/null || true
        sed -i '' '/# Vibe Coding Control Center - Loader/,+1 d' "$rc_file" 2>/dev/null || true
        # Delete PATH export following Vibe Local Bin marker
        sed -i '' '/# Vibe Local Bin/,+1 d' "$rc_file" 2>/dev/null || true
        sed -i '' '/# Vibe Direnv Hook/,+1 d' "$rc_file" 2>/dev/null || true
        sed -i '' '/^export VIBE_ROOT=/d' "$rc_file" 2>/dev/null || true
        sed -i '' '/^export UV_PROJECT_ENVIRONMENT=.*vibe-center/d' "$rc_file" 2>/dev/null || true
    else
        # Linux sed
        sed -i '/# Vibe Center - codeagent-wrapper PATH/,+1 d' "$rc_file" 2>/dev/null || true
        sed -i '/# Load Vibe keys/,+5 d' "$rc_file" 2>/dev/null || true
        sed -i '/# Vibe Coding Control Center - Loader/,+1 d' "$rc_file" 2>/dev/null || true
        # Delete PATH export following Vibe Local Bin marker
        sed -i '/# Vibe Local Bin/,+1 d' "$rc_file" 2>/dev/null || true
        sed -i '/# Vibe Direnv Hook/,+1 d' "$rc_file" 2>/dev/null || true
        sed -i '/^export VIBE_ROOT=/d' "$rc_file" 2>/dev/null || true
        sed -i '/^export UV_PROJECT_ENVIRONMENT=.*vibe-center/d' "$rc_file" 2>/dev/null || true
    fi

    log_success "Cleaned $rc_file (backup: $rc_file.vibe-backup)"
}

# Clean common shell config files
_clean_rc_file "$HOME/.zshrc"
_clean_rc_file "$HOME/.bashrc"
_clean_rc_file "$HOME/.bash_profile"

# 5. Finalize
echo ""
log_success "Uninstall complete!"
echo ""
echo "Next steps:"
echo "  1. Restart your shell or run: ${CYAN}source ~/.zshrc${NC} (or ~/.bashrc)"
echo "  2. Remove backup files if desired: ${CYAN}rm ~/.zshrc.vibe-backup${NC}"
echo ""

if [[ "$KEEP_DATA" == true ]]; then
    echo "Preserved user data:"
    echo "  - $INSTALL_DIR/config/keys.env"
    echo "  - $INSTALL_DIR/skills.json"
    echo ""
fi
