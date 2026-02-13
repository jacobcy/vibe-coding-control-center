#!/usr/bin/env zsh
# Modern Installation Script for Vibe Coding Control Center
# This script acts as a master orchestrator, delegating to specialized installers.

if [ -z "${ZSH_VERSION:-}" ]; then
    if command -v zsh >/dev/null 2>&1; then
        export VIBE_ZSH_BOOTSTRAP=1
        exec zsh -l "$0" "$@"
    fi
    # If zsh is not found, we will try to install it later or fail
    # But for the bootstrap to work, we need zsh.
    echo "zsh not found. Please install zsh manually." >&2
    exit 1
fi

set -e

# ================= SETUP =================
SCRIPT_DIR="$(cd "$(dirname "${(%):-%x}")" && pwd)"
source "$SCRIPT_DIR/../lib/utils.sh"
source "$SCRIPT_DIR/../lib/config.sh"
source "$SCRIPT_DIR/../lib/config_init.sh"
source "$SCRIPT_DIR/../lib/i18n.sh"

# ================= ARGUMENT PARSING =================
MODE=""
FORCE="false"

# Use a loop to parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --global|-g)
            if [[ -n "$MODE" && "$MODE" != "global" ]]; then
                log_warn "Conflicting modes specified. Overriding $MODE with global."
            fi
            MODE="global"
            shift
            ;;
        --local|-l)
            if [[ -n "$MODE" && "$MODE" != "local" ]]; then
                log_warn "Conflicting modes specified. Overriding $MODE with local."
            fi
            MODE="local"
            shift
            ;;
        --force|-f)
            FORCE="true"
            shift
            ;;
        *)
            log_warn "Unknown option: $1"
            shift
            ;;
    esac
done

# ================= INTERACTIVE MODE =================
if [[ -z "$MODE" ]]; then
    echo "请选择安装模式："
    echo "1. 全局安装 (Global) - 建议在主分支 (main) 目录下使用，以便多分支同步开发。"
    echo "2. 局部安装 (Local) - 建议在开发分支目录下使用，以避免影响其他分支。"
    
    while [[ -z "$MODE" ]]; do
        printf "请输入您的选择 (1/2): "
        read -r choice
        case "$choice" in
            1)
                MODE="global"
                ;;
            2)
                MODE="local"
                ;;
            *)
                echo "无效的选择，请重新输入 (1 或 2)。"
                ;;
        esac
    done
fi

log_step "Starting Vibe Coding Control Center Installation ($MODE mode)"

# ================= PREREQUISITES =================
log_step "Checking Prerequisites"
REQUIRED_TOOLS=("git" "zsh" "curl" "jq" "tmux" "lazygit")
MISSING_TOOLS=()

for tool in "${REQUIRED_TOOLS[@]}"; do
    if ! command -v "$tool" &> /dev/null; then
        MISSING_TOOLS+=("$tool")
    fi
done

if ((${#MISSING_TOOLS[@]} > 0)); then
    log_info "Missing tools: ${MISSING_TOOLS[*]}"
    if confirm_action "Install missing prerequisites?" "y"; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
             if command -v brew &> /dev/null; then
                brew install "${MISSING_TOOLS[@]}"
             else
                log_error "Homebrew not found. Please install manually."
                exit 1
             fi
        else
            # Simplified linux support for now
            log_warn "Automatic dependency installation is best supported on macOS (Brew). Please install: ${MISSING_TOOLS[*]}"
        fi
    fi
fi

ensure_zsh_installed
ensure_oh_my_zsh || true

# ================= GIT CONFIGURATION =================
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    log_step "Configuring Git Worktree Support"
    if [[ "$(git config extensions.worktreeConfig)" != "true" ]]; then
        log_info "Enabling extensions.worktreeConfig for better worktree isolation..."
        git config extensions.worktreeConfig true
    else
        log_info "Git worktree config extension is already enabled."
    fi
fi

# ================= INSTALLATION =================
SOURCE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [[ "$MODE" == "global" ]]; then
    # Global Installation: Copy to ~/.vibe
    INSTALL_DIR="$HOME/.vibe"
    log_step "Initializing Vibe Global Installation in $INSTALL_DIR"
    
    mkdir -p "$INSTALL_DIR"
    
    # Copy project files
    log_info "Copying project files to $INSTALL_DIR..."
    for dir in bin lib scripts config; do
        if [[ -d "$SOURCE_ROOT/$dir" ]]; then
            rm -rf "$INSTALL_DIR/$dir"
            cp -r "$SOURCE_ROOT/$dir" "$INSTALL_DIR/"
        fi
    done
    
    # Handle keys.env (Directly in ~/.vibe/keys.env)
    TARGET_KEYS="$INSTALL_DIR/keys.env"
    SOURCE_KEYS="$SOURCE_ROOT/config/keys.env"
    TEMPLATE_KEYS="$SOURCE_ROOT/config/keys.template.env"
    
    if [[ ! -f "$TARGET_KEYS" || "$FORCE" == "true" ]]; then
        if [[ -f "$TARGET_KEYS" ]]; then
             log_warn "Overwriting existing keys.env due to --force"
        fi

        if [[ -f "$SOURCE_KEYS" ]]; then
             log_info "Updating keys.env from local config..."
             cp "$SOURCE_KEYS" "$TARGET_KEYS"
             chmod 600 "$TARGET_KEYS"
        elif [[ -f "$TEMPLATE_KEYS" ]]; then
             log_info "Initializing keys.env from template..."
             cp "$TEMPLATE_KEYS" "$TARGET_KEYS"
             chmod 600 "$TARGET_KEYS"
             log_warn "Please edit $TARGET_KEYS to add your API keys."
        fi
    else
        log_info "Existing keys.env found at $TARGET_KEYS, keeping it. Use --force to overwrite."
    fi
    
    # Symlink aliases.sh
    # Global: ~/.vibe/aliases.sh -> ~/.vibe/config/aliases.sh
    ln -sf "$INSTALL_DIR/config/aliases.sh" "$INSTALL_DIR/aliases.sh"
    
    # Symlink vibe executable to ~/bin/vibe for convenience
    if [[ ! -d "$HOME/bin" ]]; then
        mkdir -p "$HOME/bin"
    fi
    ln -sf "$INSTALL_DIR/bin/vibe" "$HOME/bin/vibe"
    log_info "Linked vibe executable to $HOME/bin/vibe"
    
    VIBE_BIN="$INSTALL_DIR/bin"

else
    # Local Installation: Use current directory
    log_step "Initializing Vibe Local Installation in $SOURCE_ROOT"
    
    # --- Guard: require global install first ---
    if [[ ! -f "$HOME/.vibe/loader.sh" ]]; then
        log_error "Global installation not found."
        log_info "Local install requires a prior global install to set up shell integration."
        log_info ""
        log_info "Please run from the main branch first:"
        log_info "  cd /path/to/main && zsh scripts/install.sh --global"
        log_info ""
        log_info "Then come back and run:"
        log_info "  zsh scripts/install.sh --local"
        exit 1
    fi
    
    VIBE_ROOT="$SOURCE_ROOT"
    VIBE_BIN="$VIBE_ROOT/bin"
    VIBE_HOME="$VIBE_ROOT/.vibe"
    
    mkdir -p "$VIBE_HOME"
    
    # Sync keys to .vibe/keys.env
    if ! sync_keys_env "$VIBE_ROOT"; then
        log_error "Installation requires a configured keys.env"
        log_info "Please create $VIBE_ROOT/config/keys.env and run install again"
        exit 1
    fi
    
    # Symlink aliases.sh
    # Local: .vibe/aliases.sh -> config/aliases.sh
    ALIASES_LINK="$VIBE_HOME/aliases.sh"
    ALIASES_TARGET="$VIBE_ROOT/config/aliases.sh"
    rm -f "$ALIASES_LINK"
    ln -s "$ALIASES_TARGET" "$ALIASES_LINK"
fi

# ================= BOOTSTRAP 'vibe' COMMAND =================

log_step "Bootstrapping 'vibe' command"
SHELL_RC=$(get_shell_rc)

chmod +x "$VIBE_BIN/vibe"
chmod +x "$VIBE_BIN"/* 2>/dev/null || true

# --- Clean up ALL old Vibe entries from shell RC (comprehensive) ---
if [[ -f "$SHELL_RC" ]]; then
    _need_cleanup=false
    if grep -qE '(Vibe Coding Control Center|Load Vibe aliases|vibe-center|\.vibe/aliases\.sh|\.vibe/bin|\.vibe/loader\.sh)' "$SHELL_RC" 2>/dev/null; then
        _need_cleanup=true
    fi

    if $_need_cleanup; then
        log_info "Cleaning up old Vibe configuration from $SHELL_RC"

        if [[ "$OSTYPE" == "darwin"* ]]; then
            # Remove all known Vibe markers and hardcoded paths
            sed -i '' '/# Vibe Coding Control Center/d' "$SHELL_RC"
            sed -i '' '/# Load Vibe aliases/d' "$SHELL_RC"
            sed -i '' '/# Added by Antigravity/d' "$SHELL_RC"
            sed -i '' '/aliases\.sh auto-detects VIBE_ROOT/d' "$SHELL_RC"
            sed -i '' '/export PATH=".*\.vibe\/bin:\$PATH"/d' "$SHELL_RC"
            sed -i '' '/export PATH=".*vibe-center.*\/bin:\$PATH"/d' "$SHELL_RC"
            sed -i '' '/source .*\.vibe\/aliases\.sh/d' "$SHELL_RC"
            sed -i '' '/source .*\.vibe\/loader\.sh/d' "$SHELL_RC"
            sed -i '' '/\[ -f .*\.vibe\/aliases\.sh/d' "$SHELL_RC"
            sed -i '' '/\[ -f .*\.vibe\/loader\.sh/d' "$SHELL_RC"
            sed -i '' '/if \[ -f .*\.vibe\/aliases\.sh/d' "$SHELL_RC"
            sed -i '' '/if \[ -f .*\.vibe\/loader\.sh/d' "$SHELL_RC"
            # Clean up orphaned fi and blank lines left by removed blocks
            # (sed multi-pass to collapse consecutive blank lines)
        else
            sed -i '/# Vibe Coding Control Center/d' "$SHELL_RC"
            sed -i '/# Load Vibe aliases/d' "$SHELL_RC"
            sed -i '/# Added by Antigravity/d' "$SHELL_RC"
            sed -i '/aliases\.sh auto-detects VIBE_ROOT/d' "$SHELL_RC"
            sed -i '/export PATH=".*\.vibe\/bin:\$PATH"/d' "$SHELL_RC"
            sed -i '/export PATH=".*vibe-center.*\/bin:\$PATH"/d' "$SHELL_RC"
            sed -i '/source .*\.vibe\/aliases\.sh/d' "$SHELL_RC"
            sed -i '/source .*\.vibe\/loader\.sh/d' "$SHELL_RC"
            sed -i '/\[ -f .*\.vibe\/aliases\.sh/d' "$SHELL_RC"
            sed -i '/\[ -f .*\.vibe\/loader\.sh/d' "$SHELL_RC"
            sed -i '/if \[ -f .*\.vibe\/aliases\.sh/d' "$SHELL_RC"
            sed -i '/if \[ -f .*\.vibe\/loader\.sh/d' "$SHELL_RC"
        fi
        log_info "Old Vibe configuration removed"
    fi
fi

if [[ "$MODE" == "global" ]]; then
    # --- Global: install loader.sh + write stable entry to shell RC ---
    
    # Copy loader.sh to ~/.vibe/loader.sh
    LOADER_SRC="$SOURCE_ROOT/config/loader.sh"
    LOADER_DST="$INSTALL_DIR/loader.sh"
    if [[ -f "$LOADER_SRC" ]]; then
        cp "$LOADER_SRC" "$LOADER_DST"
        chmod 644 "$LOADER_DST"
        log_info "Installed loader.sh to $LOADER_DST"
    else
        log_warn "loader.sh not found at $LOADER_SRC — creating inline"
        cat > "$LOADER_DST" << 'LOADER_EOF'
#!/usr/bin/env zsh
# Vibe Coding Control Center - Unified Shell Loader
export PATH="$HOME/.vibe/bin:$PATH"
if [[ -d "$PWD/.vibe" && -d "$PWD/bin" ]]; then
    export PATH="$PWD/bin:$PATH"
fi
if [[ -f "$HOME/.vibe/aliases.sh" ]]; then
    source "$HOME/.vibe/aliases.sh"
fi
LOADER_EOF
        chmod 644 "$LOADER_DST"
    fi

    # Write a single stable line to shell RC
    RC_CONTENT='# Vibe Coding Control Center
[ -f "$HOME/.vibe/loader.sh" ] && source "$HOME/.vibe/loader.sh"
'
    append_to_rc "$SHELL_RC" "$RC_CONTENT" "Vibe Coding Control Center"
    log_success "'vibe' command is ready (Mode: global)"

else
    # --- Local: do NOT modify ~/.zshrc ---
    log_info "Local install: skipping shell RC modification"
    log_info "Use 'source $VIBE_HOME/aliases.sh' in this session, or"
    log_info "run 'install.sh --global' from main branch to set up permanent aliases."
    log_success "'vibe' command is ready (Mode: local, bin at $VIBE_BIN)"
fi

# ================= FINAL SUMMARY =================
log_success "Installation process completed!"

echo -e "\n${BOLD}NEXT STEPS:${NC}"
if [[ "$MODE" == "global" ]]; then
    echo "1. Reload shell: ${CYAN}source $SHELL_RC${NC} (or restart terminal)"
    echo "2. Verify: ${CYAN}vibe --help${NC}"
    echo "3. Install AI tools: ${CYAN}vibe equip${NC}"
    echo "4. Launch Control Center: ${CYAN}vibe${NC}"
else
    echo "1. Source aliases for this session: ${CYAN}source $VIBE_HOME/aliases.sh${NC}"
    echo "2. Verify: ${CYAN}vibe --help${NC}"
    echo "3. (Optional) Run global install from main: ${CYAN}cd main && zsh scripts/install.sh --global${NC}"
fi
echo "----------------------------------------"
