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
    if grep -qF "$marker" "$rc_file" 2>/dev/null || grep -qF "$content" "$rc_file" 2>/dev/null; then
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

_get_direnv_hook() {
    case "$SHELL" in
        */bash) echo 'eval "$(direnv hook bash)"' ;;
        *) echo 'eval "$(direnv hook zsh)"' ;;
    esac
}

_setup_gh_noninteractive() {
    log_step "Setting up GitHub CLI defaults..."

    if ! command -v gh &> /dev/null; then
        log_info "gh not installed, skipping non-interactive setup"
        return 0
    fi

    gh config set prompt disabled >/dev/null 2>&1 || log_warn "Failed to set gh prompt=disabled"
    gh config set pager cat >/dev/null 2>&1 || log_warn "Failed to set gh pager=cat"
    log_success "Configured gh for non-interactive mode"
}

VIBE_UV_BIN=""

_ensure_uv_cli() {
    local local_bin="$HOME/.local/bin"
    local local_uv="$local_bin/uv"
    local system_uv=""

    mkdir -p "$local_bin"
    export PATH="$local_bin:$PATH"

    if [[ -x "$local_uv" ]]; then
        VIBE_UV_BIN="$local_uv"
        return 0
    fi

    if command -v uv >/dev/null 2>&1; then
        system_uv="$(command -v uv)"
    fi

    log_info "Ensuring uv is installed at $local_uv ..."

    if command -v curl >/dev/null 2>&1; then
        if ! curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$local_bin" sh >/dev/null 2>&1; then
            log_warn "Failed to install uv via curl installer."
        fi
    elif command -v wget >/dev/null 2>&1; then
        if ! wget -qO- https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$local_bin" sh >/dev/null 2>&1; then
            log_warn "Failed to install uv via wget installer."
        fi
    elif [[ -z "$system_uv" ]]; then
        log_warn "Neither curl nor wget is available, cannot auto-install uv."
    fi

    if [[ -x "$local_uv" ]]; then
        VIBE_UV_BIN="$local_uv"
        log_success "Installed uv at $local_uv"
        return 0
    fi

    if [[ -n "$system_uv" ]]; then
        VIBE_UV_BIN="$system_uv"
        log_warn "Falling back to system uv at $system_uv (local install unavailable)."
        return 0
    fi

    log_warn "uv installation finished but executable not found at $local_uv"
    return 1
}

# --- Main Flow ---
log_step "Installing Vibe Center (Global)"

# 1. Create directory structure
log_info "Setting up $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR/bin" "$INSTALL_DIR/lib" "$INSTALL_DIR/config" "$INSTALL_DIR/scripts" "$INSTALL_DIR/alias"

# 2. Sync core components (Copying to ensure global persistence)
log_info "Syncing core modules..."
for dir in bin lib lib3 config scripts alias; do
    [[ -d "$SOURCE_ROOT/$dir" ]] || continue
    mkdir -p "$INSTALL_DIR/$dir"
    # Copy directory contents portably so GNU/BSD cp do not create nested dir/dir trees.
    cp -R "$SOURCE_ROOT/$dir/." "$INSTALL_DIR/$dir/"
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

# 6. GitHub CLI defaults (non-interactive)
_setup_gh_noninteractive

# 7. Direnv Setup (auto-configure if direnv is installed)
_setup_direnv() {
    log_step "Setting up direnv..."

    # Check if direnv is installed
    if ! command -v direnv &> /dev/null; then
        log_info "direnv not installed, skipping direnv integration"
        return 0
    fi

    # Add direnv hook to RC file
    local direnv_hook
    direnv_hook="$(_get_direnv_hook)"
    if ! grep -qF 'direnv hook zsh' "$RC_FILE" 2>/dev/null; then
        _append_to_rc "$RC_FILE" "$direnv_hook" "direnv"
        log_info "Added direnv hook to $RC_FILE"
    else
        log_info "direnv hook already present in $RC_FILE"
    fi

    # Create .envrc in source root if not exists
    local envrc_path="$SOURCE_ROOT/.envrc"
    if [[ ! -f "$envrc_path" ]]; then
        log_info "Creating $envrc_path..."
        echo 'source "$HOME/.venvs/vibe-center/bin/activate"' > "$envrc_path"
    else
        log_info ".envrc already exists at $envrc_path"
    fi

    # Allow direnv (in source root)
    log_info "Running direnv allow..."
    cd "$SOURCE_ROOT"
    direnv allow 2>/dev/null || log_warn "direnv allow failed (may need manual approval)"

    log_success "direnv setup complete!"
}

_setup_uv_environment() {
    log_step "Setting up uv environment..."

    _append_to_rc "$RC_FILE" 'export PATH="$HOME/.local/bin:$PATH"' "Vibe Local Bin"

    if ! _ensure_uv_cli; then
        log_warn "uv setup incomplete; skipping venv bootstrap."
        return 0
    fi

    local venv_path="$HOME/.venvs/vibe-center"
    if [[ ! -d "$venv_path" ]]; then
        log_info "Creating global venv at $venv_path..."
        mkdir -p "$HOME/.venvs"
        "$VIBE_UV_BIN" venv "$venv_path"
    else
        log_info "Global venv already exists at $venv_path"
    fi

    local uv_env_export='export UV_PROJECT_ENVIRONMENT="$HOME/.venvs/vibe-center"'
    _append_to_rc "$RC_FILE" "$uv_env_export" "UV_PROJECT_ENVIRONMENT"

    if [[ -n "$UV_PROJECT_ENVIRONMENT" && "$UV_PROJECT_ENVIRONMENT" != "$venv_path" && "$UV_PROJECT_ENVIRONMENT" != "\$HOME/.venvs/vibe-center" ]]; then
        log_warn "Current UV_PROJECT_ENVIRONMENT differs: $UV_PROJECT_ENVIRONMENT"
        log_warn "Recommended value: $venv_path"
    fi

    log_success "uv environment setup complete."
}

# Auto-run uv + direnv setup
_setup_uv_environment
_setup_direnv

# 8. Finalize
chmod +x "$INSTALL_DIR/bin/vibe"
log_success "Installation complete!"

echo -e "\n${BOLD}NEXT STEPS:${NC}"
echo "1. Reload shell: ${CYAN}source $RC_FILE${NC}"
echo "2. Run diagnostics: ${CYAN}vibe doctor${NC}"
echo "3. Happy Coding! ${CYAN}vibe --help${NC}"
echo "----------------------------------------"
