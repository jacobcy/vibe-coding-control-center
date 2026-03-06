#!/usr/bin/env zsh
# Vibe Coding Control Center - Minimalist Installer (v2)
# Replaces 300+ lines of legacy logic with a streamlined bootstrapper.

set -e

# --- Configuration ---
INSTALL_DIR="$HOME/.vibe"
SOURCE_ROOT="$(cd "$(dirname "${(%):-%x}")/.." && pwd)"
[[ -f "$SOURCE_ROOT/lib/utils.sh" ]] && source "$SOURCE_ROOT/lib/utils.sh" || { echo "error: missing lib/utils.sh"; exit 1; }

# --- Help ---
_usage() {
    echo "${BOLD}Vibe Coding Control Center - Installer${NC}"
    echo ""
    echo "此脚本负责 Vibe 的全局分发与环境初始化："
    echo "  1. 建立分发轨道：同步核心组件 (bin/lib/config/scripts) 到 ${CYAN}~/.vibe${NC}"
    echo "  2. 密钥托管：从模板初始化全局 ${CYAN}keys.env${NC} 配置文件"
    echo "  3. 注入加载器：在 ${CYAN}.zshrc/.bashrc${NC} 中建立全量加载链路 (loader.sh)"
    echo ""
    echo "Usage: ${CYAN}scripts/install.sh${NC} [options]"
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

# --- Helpers ---
_append_to_rc() {
    local rc_file="$1" content="$2" marker="$3"
    [[ -f "$rc_file" ]] || touch "$rc_file"
    if grep -qF "$marker" "$rc_file" 2>/dev/null; then
        log_info "Configuration already present in $rc_file"
    else
        echo -e "\n# $marker\n$content" >> "$rc_file"
        log_success "Added to $rc_file"
    fi
}

_get_shell_rc() {
    case "$SHELL" in
        */zsh) echo "$HOME/.zshrc" ;;
        */bash) echo "$HOME/.bashrc" ;;
        *) echo "$HOME/.zshrc" ;; # Default to zsh
    esac
}

# --- Main Flow ---
log_step "Installing Vibe Center (Global)"

# 1. Create directory structure
log_info "Setting up $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR/bin" "$INSTALL_DIR/lib" "$INSTALL_DIR/config"

# 2. Sync core components (Copying to ensure global persistence)
log_info "Syncing core modules..."
for dir in bin lib config scripts; do
    [[ -d "$SOURCE_ROOT/$dir" ]] || continue
    cp -r "$SOURCE_ROOT/$dir/" "$INSTALL_DIR/$dir/"
done

# 3. Handle Key Template
if [[ ! -f "$INSTALL_DIR/keys.env" ]]; then
    log_info "Initializing keys.env from template..."
    cp "$SOURCE_ROOT/config/keys.template.env" "$INSTALL_DIR/keys.env"
    chmod 600 "$INSTALL_DIR/keys.env"
fi

# 4. Bootstrap loader.sh
LOADER_DST="$INSTALL_DIR/loader.sh"
log_info "Installing loader at $LOADER_DST..."
cp "$SOURCE_ROOT/config/loader.sh" "$LOADER_DST"
chmod 755 "$LOADER_DST"

# 5. Shell Integration
RC_FILE="$(_get_shell_rc)"
log_info "Updating $RC_FILE..."

# Cleanup old markers if they exist (Basic cleanup for transition)
if [[ -f "$RC_FILE" ]]; then
    sed -i '' '/# Vibe Coding Control Center/d' "$RC_FILE" 2>/dev/null || sed -i '/# Vibe Coding Control Center/d' "$RC_FILE" 2>/dev/null || true
    sed -i '' '/source .*\/loader.sh/d' "$RC_FILE" 2>/dev/null || sed -i '/source .*\/loader.sh/d' "$RC_FILE" 2>/dev/null || true
fi

_append_to_rc "$RC_FILE" "[ -f \"$INSTALL_DIR/loader.sh\" ] && source \"$INSTALL_DIR/loader.sh\"" "Vibe Coding Control Center"

# 6. Direnv Setup (auto-configure if direnv is installed)
_setup_direnv() {
    log_step "Setting up direnv..."

    # Check if direnv is installed
    if ! command -v direnv &> /dev/null; then
        log_info "direnv not installed, skipping auto-venv setup"
        return 0
    fi

    # Add direnv hook to RC file
    local direnv_hook='eval "$(direnv hook zsh)"'
    if ! grep -qF 'direnv hook zsh' "$RC_FILE" 2>/dev/null; then
        _append_to_rc "$RC_FILE" "$direnv_hook" "direnv"
        log_info "Added direnv hook to $RC_FILE"
    else
        log_info "direnv hook already present in $RC_FILE"
    fi

    # Create global venv if not exists
    local venv_path="$HOME/.venvs/vibe-center"
    if [[ ! -d "$venv_path" ]]; then
        log_info "Creating global venv at $venv_path..."
        mkdir -p "$HOME/.venvs"
        uv venv "$venv_path"
    else
        log_info "Global venv already exists at $venv_path"
    fi

    # Create .envrc in source root if not exists
    local envrc_path="$SOURCE_ROOT/.envrc"
    if [[ ! -f "$envrc_path" ]]; then
        log_info "Creating $envrc_path..."
        echo "source $venv_path/bin/activate" > "$envrc_path"
    else
        log_info ".envrc already exists at $envrc_path"
    fi

    # Allow direnv (in source root)
    log_info "Running direnv allow..."
    cd "$SOURCE_ROOT"
    direnv allow 2>/dev/null || log_warn "direnv allow failed (may need manual approval)"

    log_success "direnv setup complete!"
}

# Auto-run direnv setup if direnv is installed
_setup_direnv

# 7. Finalize
chmod +x "$INSTALL_DIR/bin/vibe"
log_success "Installation complete!"

echo -e "\n${BOLD}NEXT STEPS:${NC}"
echo "1. Reload shell: ${CYAN}source $RC_FILE${NC}"
echo "2. Run diagnostics: ${CYAN}vibe doctor${NC}"
echo "3. Happy Coding! ${CYAN}vibe --help${NC}"
echo "----------------------------------------"
