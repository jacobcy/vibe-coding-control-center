#!/usr/bin/env zsh
# Vibe Coding Control Center - Minimal Installer (v3)
# 只做最基础的安装和环境配置，全面检查和引导由 /vibe-onboard skill 完成

set -euo pipefail

# --- Configuration ---
INSTALL_DIR="$HOME/.vibe"
SOURCE_ROOT="$(cd "$(dirname "${(%):-%x}")/.." && pwd)"
[[ -f "$SOURCE_ROOT/lib/utils.sh" ]] && source "$SOURCE_ROOT/lib/utils.sh" || { echo "error: missing lib/utils.sh"; exit 1; }
[[ -f "$SOURCE_ROOT/lib/install_utils.sh" ]] && source "$SOURCE_ROOT/lib/install_utils.sh"

# --- Help ---
_usage() {
    echo "${BOLD}Vibe Coding Control Center - Installer${NC}"
    echo ""
    echo "此脚本负责 Vibe 的基础环境初始化："
    echo "  1. 建立分发轨道：同步核心组件到 ${CYAN}~/.vibe${NC}"
    echo "  2. 密钥托管：从模板初始化全局 ${CYAN}keys.env${NC} 配置文件"
    echo "  3. 依赖安装：安装 uv 与基础 Python 环境"
    echo "  4. 提交 .envrc：共享 venv + 本地 src 配置（已提交到仓库）"
    echo "  5. 注入加载器：在 shell 配置文件中建立全量加载链路"
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

_write_file_if_changed() {
    local path="$1"
    local content="$2"
    local current=""
    [[ -f "$path" ]] && current="$(<"$path")"
    if [[ "$current" != "$content" ]]; then
        printf '%s\n' "$content" > "$path"
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

_validate_venv() {
    local venv_path="$1"
    [[ -f "$venv_path/pyvenv.cfg" ]] && [[ -x "$venv_path/bin/python" ]]
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

_add_vibe_dir_to_direnv_whitelist() {
    local DIRENV_CONF_DIR="$HOME/.config/direnv"
    local DIRENV_CONF="$DIRENV_CONF_DIR/direnv.toml"
    local WHITELIST_ENTRY="${HOME}/.vibe"

    if ! command -v direnv >/dev/null 2>&1; then
        log_info "direnv not installed, skip whitelist"
        return 0
    fi

    if [[ -f "$DIRENV_CONF" ]]; then
        # Full-quote match: only consider the entry already registered in a prefix
        # array (avoids false-positive substring hits on sibling paths).
        if grep -qF "\"$WHITELIST_ENTRY\"" "$DIRENV_CONF"; then
            log_info "direnv whitelist already contains $WHITELIST_ENTRY"
            return 0
        fi
    fi

    mkdir -p "$DIRENV_CONF_DIR"

    local tmp="$DIRENV_CONF.tmp.$$.whitelist"
    if [[ -f "$DIRENV_CONF" ]]; then
        # Merge every prefix entry seen under any [whitelist] block into a single
        # consolidated section. Appending a second [whitelist] block would produce
        # invalid TOML for strict parsers (e.g. Python tomllib rejects duplicate
        # table keys), so we collapse all existing entries + the new one into one.
        # stripqs() trims the first/last double-quote of each entry using
        # position-based substr: BSD/macOS awk 20200816 drops the $ anchor when
        # gsub() is called with an alternation like /^["]+|["]+$/ on inputs that
        # begin with a non-" character (leading whitespace before the opening DQ).
        local awk_body
        awk_body="$(cat <<'AWKEOF'
BEGIN {
    print "# auto-added by scripts/install.sh (vibe)"
    in_wl = 0
    flushed = 0
    acc = ""
    seen_count = 0
    new_already = 0
}
function stripqs(s,    first, last, i) {
    first = 0
    last = 0
    for (i = 1; i <= length(s); i++) {
        if (substr(s, i, 1) == "\"") {
            if (first == 0) first = i
            last = i
        }
    }
    if (first == 0) return s
    if (first == last) {
        return substr(s, 1, first-1) substr(s, first+1)
    }
    return substr(s, 1, first-1) substr(s, first+1, last-first-1) substr(s, last+1)
}
function add_entry(p) {
    p = stripqs(p)
    sub(/^[[:space:]]+|[[:space:]]+$/, "", p)
    if (p == "") return
    seen_count++
    seen[seen_count] = p
    if (p == entry) new_already = 1
}
function add_entries_from(line,    raw, n, i, part) {
    raw = line
    sub(/^[[:space:]]*prefix[[:space:]]*=[[:space:]]*\[?/, "", raw)
    sub(/\]?[[:space:]]*$/, "", raw)
    if (raw == "") return
    n = split(raw, parts, ",")
    for (i = 1; i <= n; i++) add_entry(parts[i])
}
function flush(    i, first) {
    if (flushed) return
    flushed = 1
    printf "[whitelist]\nprefix = ["
    first = 1
    for (i = 1; i <= seen_count; i++) {
        if (!first) printf ", "
        printf "\"%s\"", seen[i]
        first = 0
    }
    if (!new_already) {
        if (!first) printf ", "
        printf "\"%s\"", entry
    }
    printf "]\n"
}
/^[[:space:]]*\[/ {
    if (in_wl) { flush(); in_wl = 0 }
    if ($0 ~ /^[[:space:]]*\[whitelist\][[:space:]]*$/) { in_wl = 1; next }
    in_wl = 0
    print
    next
}
in_wl {
    line = $0
    gsub(/^[[:space:]]+/, "", line)
    if (acc != "") acc = acc " " line; else acc = line
    if (line ~ /\][[:space:]]*$/) {
        if (acc ~ /prefix[[:space:]]*=/) add_entries_from(acc)
        acc = ""
    }
    next
}
{ print }
END { flush() }
AWKEOF
)"
        if ! awk -v entry="$WHITELIST_ENTRY" "$awk_body" "$DIRENV_CONF" > "$tmp" 2>/dev/null; then
            cp "$DIRENV_CONF" "$tmp"
        fi
    else
        {
            echo "# auto-added by scripts/install.sh (vibe)"
            echo "[whitelist]"
            echo "prefix = [\"$WHITELIST_ENTRY\"]"
        } > "$tmp"
    fi
    if mv "$tmp" "$DIRENV_CONF"; then
        log_success "Added $WHITELIST_ENTRY to direnv whitelist ($DIRENV_CONF)"
    else
        rm -f "$tmp"
        log_warn "Failed to update direnv whitelist — please add manually: $WHITELIST_ENTRY"
        return 0
    fi
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
for dir in bin lib lib3 config scripts alias src skills supervisor; do
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

# 3.5 Clean stale files in synced directories
_clean_stale_in_dir() {
    local src_dir="$1"
    local dst_dir="$2"
    local cleaned=0
    while IFS= read -r -d '' file; do
        local rel_path="${file#$dst_dir/}"
        local src_path="$src_dir/$rel_path"
        if [[ ! -e "$src_path" ]]; then
            rm -f "$file"
            cleaned=$((cleaned + 1))
        fi
    done < <(find "$dst_dir" -type f -print0 2>/dev/null)
    # Clean empty directories left behind
    find "$dst_dir" -type d -empty -delete 2>/dev/null || true
    if [[ $cleaned -gt 0 ]]; then
        log_info "Cleaned $cleaned stale file(s)"
    fi
}

for dir in bin lib lib3 config scripts src skills supervisor; do
    if [[ -d "$SOURCE_ROOT/$dir" && -d "$INSTALL_DIR/$dir" ]]; then
        _clean_stale_in_dir "$SOURCE_ROOT/$dir" "$INSTALL_DIR/$dir"
    fi
done

# NOTE: install.sh only handles first-time setup (bootstrap).
# Subsequent global updates use: vibe update
# Project/worktree initialization uses: scripts/init.sh

# 4. Handle Key Template
if [[ ! -f "$INSTALL_DIR/config/keys.env" ]]; then
    log_info "Initializing keys.env from template..."
    cp "$SOURCE_ROOT/config/keys.template.env" "$INSTALL_DIR/config/keys.env"
    chmod 600 "$INSTALL_DIR/config/keys.env"
fi

# 4.5 Runtime assets (supervisor/policies, config/prompts) are now synced as core components
# No separate sync needed - supervisor/ and config/ are in the core sync list above

# 4.6 Generate global settings.yaml with path overrides
if [[ ! -f "$INSTALL_DIR/settings.yaml" ]]; then
    log_info "Generating global settings.yaml..."
    cat > "$INSTALL_DIR/settings.yaml" << 'EOF'
# Vibe Center Global Configuration
# =================================
# 此文件由 scripts/install.sh 自动生成，提供全局路径配置覆盖
# 项目级配置（.vibe/settings.yaml）优先级高于此文件

# Paths Configuration
# Canonical runtime asset paths (synced from supervisor/ and config/)
paths:
  policies_root: "$HOME/.vibe/supervisor/policies"
  prompts_root: "$HOME/.vibe/config/prompts"

# 其他配置项继承自 repo 的 config/v3/settings.yaml
EOF
    # Replace $HOME with actual home path
    sed -i.bak "s|\$HOME|$HOME|g" "$INSTALL_DIR/settings.yaml" && rm -f "$INSTALL_DIR/settings.yaml.bak"
    chmod 644 "$INSTALL_DIR/settings.yaml"
    log_success "Global settings.yaml generated"
else
    _migrate_settings_yaml_paths "$INSTALL_DIR"
fi

# 4.7 Sync canonical skills manifest
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
        sed -i '' '/# Vibe Center - codeagent-wrapper PATH/,+1 d' "$RC_FILE" 2>/dev/null || true
        sed -i '' '/# Load Vibe keys/,+5 d' "$RC_FILE" 2>/dev/null || true
        sed -i '' '/# Vibe Coding Control Center - Loader/d' "$RC_FILE" 2>/dev/null || true
        sed -i '' '/source .*\/loader.sh/d' "$RC_FILE" 2>/dev/null || true
        sed -i '' '/^export VIBE_ROOT=/d' "$RC_FILE" 2>/dev/null || true
        sed -i '' '/^export UV_PROJECT_ENVIRONMENT=.*vibe-center/d' "$RC_FILE" 2>/dev/null || true
        sed -i '' '/# Vibe Local Bin/,+1 d' "$RC_FILE" 2>/dev/null || true
        sed -i '' '/# Vibe Direnv Hook/d' "$RC_FILE" 2>/dev/null || true
        sed -i '' '/direnv hook /d' "$RC_FILE" 2>/dev/null || true
    else
        sed -i '/# Vibe Center - codeagent-wrapper PATH/,+1 d' "$RC_FILE" 2>/dev/null || true
        sed -i '/# Load Vibe keys/,+5 d' "$RC_FILE" 2>/dev/null || true
        sed -i '/# Vibe Coding Control Center - Loader/d' "$RC_FILE" 2>/dev/null || true
        sed -i '/source .*\/loader.sh/d' "$RC_FILE" 2>/dev/null || true
        sed -i '/^export VIBE_ROOT=/d' "$RC_FILE" 2>/dev/null || true
        sed -i '/^export UV_PROJECT_ENVIRONMENT=.*vibe-center/d' "$RC_FILE" 2>/dev/null || true
        sed -i '/# Vibe Local Bin/,+1 d' "$RC_FILE" 2>/dev/null || true
        sed -i '/# Vibe Direnv Hook/d' "$RC_FILE" 2>/dev/null || true
        sed -i '/direnv hook /d' "$RC_FILE" 2>/dev/null || true
    fi
fi

# 添加环境变量
_append_to_rc "$RC_FILE" 'export PATH="$HOME/.claude/bin:$PATH"' "Vibe Center - codeagent-wrapper PATH"
_append_to_rc "$RC_FILE" $'if [[ -f ~/.vibe/config/keys.env ]]; then\n    set -a\n    source ~/.vibe/config/keys.env 2>/dev/null || true\n    set +a\nfi' "Load Vibe keys"
_append_to_rc "$RC_FILE" "[ -f \"$INSTALL_DIR/loader.sh\" ] && source \"$INSTALL_DIR/loader.sh\"" "Vibe Coding Control Center - Loader"
# NOTE: Removed ~/.local/bin PATH export to prevent uv tool install conflicts
# uv automatically handles ~/.local/bin in PATH during its installation
if [[ "$SHELL" == */bash ]]; then
    _append_to_rc "$RC_FILE" 'command -v direnv >/dev/null 2>&1 && eval "$(direnv hook bash)"' "Vibe Direnv Hook"
else
    _append_to_rc "$RC_FILE" 'command -v direnv >/dev/null 2>&1 && eval "$(direnv hook zsh)"' "Vibe Direnv Hook"
fi

if command -v gh >/dev/null 2>&1; then
    gh config set prompt disabled >/dev/null 2>&1 || true
    gh config set pager cat >/dev/null 2>&1 || true
fi

# 7. uv环境与Python依赖安装
_setup_uv_environment() {
    log_step "Setting up uv environment..."

    if ! _ensure_uv_cli; then
        log_error "uv setup failed, cannot proceed with Python environment"
        exit 1
    fi

    local venv_path="$HOME/.venvs/vibe-center"
    if [[ -d "$venv_path" ]]; then
        if _validate_venv "$venv_path"; then
            log_info "Global venv already exists at $venv_path"
        else
            log_warn "Global venv at $venv_path is invalid; removing and recreating..."
            if ! rm -rf "$venv_path" 2>/dev/null; then
                log_error "Failed to remove invalid venv at $venv_path"
                log_error "Please manually remove it with: rm -rf $venv_path"
                exit 1
            fi
        fi
    fi
    if [[ ! -d "$venv_path" ]]; then
        log_info "Creating global venv at $venv_path..."
        mkdir -p "$HOME/.venvs"
        "$VIBE_UV_BIN" venv "$venv_path"
    fi

    export UV_PROJECT_ENVIRONMENT="$venv_path"

    # .envrc is now committed in the repo - just ensure direnv allow
    if command -v direnv >/dev/null 2>&1; then
        (
            cd "$SOURCE_ROOT" &&
                direnv allow . >/dev/null 2>&1 || true
        )
        # Whitelist ~/.vibe so all future vibe-managed worktrees auto-activate .envrc
        _add_vibe_dir_to_direnv_whitelist || true
    fi

    # 安装项目依赖（NOT editable install）
    log_info "Installing Python dependencies..."
    cd "$SOURCE_ROOT"
    "$VIBE_UV_BIN" sync --all-extras
    log_success "Python dependencies installed"

    # Note: deps-only venv, no editable install
    log_info "Python environment ready (deps-only venv, local src resolution via cli.py bootstrap)"
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

# 8.5 Sanity check: verify critical runtime assets
_check_runtime_assets "$INSTALL_DIR"

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
