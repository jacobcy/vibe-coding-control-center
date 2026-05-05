#!/usr/bin/env zsh
# Vibe Coding Control Center - Minimal Installer (v3)
# 只做最基础的安装和环境配置，全面检查和引导由 /vibe-onboard skill 完成

set -euo pipefail

# --- Configuration ---
INSTALL_DIR="$HOME/.vibe"
SOURCE_ROOT="$(cd "$(dirname "${(%):-%x}")/.." && pwd)"
[[ -f "$SOURCE_ROOT/lib/utils.sh" ]] && source "$SOURCE_ROOT/lib/utils.sh" || { echo "error: missing lib/utils.sh"; exit 1; }

# --- Help ---
_usage() {
    echo "${BOLD}Vibe Coding Control Center - Installer${NC}"
    echo ""
    echo "此脚本负责 Vibe 的基础环境初始化："
    echo "  1. 建立分发轨道：同步核心组件到 ${CYAN}~/.vibe${NC}"
    echo "  2. 密钥托管：从模板初始化全局 ${CYAN}keys.env${NC} 配置文件"
    echo "  3. 依赖安装：安装 uv 与基础 Python 环境"
    echo "  4. 注入加载器：在 shell 配置文件中建立全量加载链路"
    echo ""
    echo "Usage: ${CYAN}scripts/install.sh${NC} [options]"
    echo ""
    echo "Options:"
    echo "  -h, --help        显示此帮助信息"
    echo ""
    exit 0
}

# 解析参数
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
        *)
            log_warn "Unsupported shell: $SHELL (loader.sh requires zsh)"
            log_info "Defaulting to zshrc - please install zsh or manually configure"
            echo "$HOME/.zshrc"
            ;;
    esac
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

    log_error "uv installation failed, cannot proceed with Python environment setup"
    return 1
}

# --- Pre-flight checks ---
log_step "Performing pre-flight checks..."
# 检查写入权限
if ! touch "$HOME/.vibe_test_write" 2>/dev/null; then
    log_error "No write permission to home directory, cannot proceed with installation"
    exit 1
fi
rm -f "$HOME/.vibe_test_write"

# 检查基本系统依赖
for cmd in git curl; do
    if ! command -v $cmd &> /dev/null; then
        log_error "Required command '$cmd' not found, please install it first"
        exit 1
    fi
done
log_success "All pre-flight checks passed"

# --- Main Flow ---
log_step "Installing Vibe Center (Global)"

# 1. 同步git子模块
log_step "Updating git submodules..."
if [[ -f "$SOURCE_ROOT/.gitmodules" ]]; then
    cd "$SOURCE_ROOT"
    git submodule update --init --recursive
    log_success "Git submodules updated"
else
    log_info "No git submodules found, skipping"
fi

# 2. Create directory structure
log_info "Setting up $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR/bin" "$INSTALL_DIR/lib" "$INSTALL_DIR/config" "$INSTALL_DIR/scripts" "$INSTALL_DIR/alias"

# 3. Sync core components (Copying to ensure global persistence)
log_info "Syncing core modules..."
for dir in bin lib lib3 config scripts alias src; do
    [[ -d "$SOURCE_ROOT/$dir" ]] || continue
    mkdir -p "$INSTALL_DIR/$dir"
    # Copy directory contents portably so GNU/BSD cp do not create nested dir/dir trees.
    cp -R "$SOURCE_ROOT/$dir/." "$INSTALL_DIR/$dir/"
done

# Sync Python project files for uv run
for file in pyproject.toml uv.lock; do
    [[ -f "$SOURCE_ROOT/$file" ]] && cp "$SOURCE_ROOT/$file" "$INSTALL_DIR/"
done
log_success "Core modules synced"

# 4. Handle Key Template
if [[ ! -f "$INSTALL_DIR/config/keys.env" ]]; then
    log_info "Initializing keys.env from template..."
    cp "$SOURCE_ROOT/config/keys.template.env" "$INSTALL_DIR/config/keys.env"
    chmod 600 "$INSTALL_DIR/config/keys.env"
fi

# 4.5 Sync canonical skills manifest
if [[ -f "$SOURCE_ROOT/config/v3/skills.json" ]]; then
    log_info "Syncing canonical skills manifest..."
    cp "$SOURCE_ROOT/config/v3/skills.json" "$INSTALL_DIR/skills.json"
    chmod 644 "$INSTALL_DIR/skills.json"
elif [[ -f "$SOURCE_ROOT/config/skills.json" ]]; then
    log_info "Syncing legacy skills manifest..."
    cp "$SOURCE_ROOT/config/skills.json" "$INSTALL_DIR/skills.json"
    chmod 644 "$INSTALL_DIR/skills.json"
fi

# 5. Bootstrap loader.sh
LOADER_DST="$INSTALL_DIR/loader.sh"
log_info "Installing loader at $LOADER_DST..."
cp "$SOURCE_ROOT/config/shell/loader.sh" "$LOADER_DST"
chmod 755 "$LOADER_DST"
log_success "Loader installed"

# 6. Shell Integration
RC_FILE="$(_get_shell_rc)"
log_info "Updating $RC_FILE..."

# Cleanup old markers if they exist
if [[ -f "$RC_FILE" ]]; then
    # 兼容macOS和Linux的sed语法
    if [[ "$(uname)" == "Darwin" ]]; then
        sed -i '' '/# Vibe Coding Control Center/d' "$RC_FILE" 2>/dev/null || true
        sed -i '' '/source .*\/loader.sh/d' "$RC_FILE" 2>/dev/null || true
        sed -i '' '/VIBE_ROOT/d' "$RC_FILE" 2>/dev/null || true
        sed -i '' '/UV_PROJECT_ENVIRONMENT/d' "$RC_FILE" 2>/dev/null || true
        sed -i '' '/Vibe Local Bin/d' "$RC_FILE" 2>/dev/null || true
    else
        sed -i '/# Vibe Coding Control Center/d' "$RC_FILE" 2>/dev/null || true
        sed -i '/source .*\/loader.sh/d' "$RC_FILE" 2>/dev/null || true
        sed -i '/VIBE_ROOT/d' "$RC_FILE" 2>/dev/null || true
        sed -i '/UV_PROJECT_ENVIRONMENT/d' "$RC_FILE" 2>/dev/null || true
        sed -i '/Vibe Local Bin/d' "$RC_FILE" 2>/dev/null || true
    fi
fi

# 添加环境变量
_append_to_rc "$RC_FILE" "export VIBE_ROOT=\"$SOURCE_ROOT\"" "Vibe Coding Control Center - Root"
_append_to_rc "$RC_FILE" "[ -f \"$INSTALL_DIR/loader.sh\" ] && source \"$INSTALL_DIR/loader.sh\"" "Vibe Coding Control Center - Loader"
_append_to_rc "$RC_FILE" 'export PATH="$HOME/.local/bin:$PATH"' "Vibe Local Bin"

# 7. uv环境与Python依赖安装
_setup_uv_environment() {
    log_step "Setting up uv environment..."

    if ! _ensure_uv_cli; then
        log_error "uv setup failed, cannot proceed with Python environment"
        exit 1
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
    export UV_PROJECT_ENVIRONMENT="$venv_path"

    # 安装项目依赖
    log_info "Installing Python dependencies..."
    cd "$SOURCE_ROOT"
    "$VIBE_UV_BIN" sync --all-extras
    log_success "Python dependencies installed"

    # 安装项目本身
    log_info "Installing Vibe CLI package..."
    "$VIBE_UV_BIN" pip install -e .
    log_success "Vibe CLI installed successfully"
}

_setup_uv_environment

# 8. Auto-initialize current project/worktree
if [[ -f "$SOURCE_ROOT/scripts/init.sh" ]]; then
    log_step "Running project initialization..."
    (
        cd "$SOURCE_ROOT" &&
            bash "$SOURCE_ROOT/scripts/init.sh"
    ) || log_warn "Project initialization failed during install; you can rerun zsh scripts/init.sh later."
fi

# 9. Finalize
chmod +x "$INSTALL_DIR/bin/vibe"
log_success "Base installation complete!"

echo -e "\n${BOLD}NEXT STEPS:${NC}"
echo "1. Reload shell: ${CYAN}source $RC_FILE${NC}"
echo "2. 进入项目后使用引导式入口：${CYAN}/vibe-onboard${NC}"
echo "3. 或手工检查：${CYAN}vibe doctor${NC} / ${CYAN}vibe keys check${NC}"
echo "4. 手动编辑密钥文件：${CYAN}\${EDITOR:-vim} ~/.vibe/config/keys.env${NC}"
echo "5. 检查 skills 体系：${CYAN}vibe skills check${NC} / ${CYAN}/vibe-skills-manager${NC}"
echo "----------------------------------------"
