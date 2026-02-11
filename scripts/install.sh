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
MODE="global"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --local)
            MODE="local"
            shift
            ;;
        *)
            # unknown option
            shift
            ;;
    esac
done

log_step "Starting Vibe Coding Control Center Installation ($MODE mode)"
SHELL_RC=$(get_shell_rc)

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
    
    if [[ ! -f "$TARGET_KEYS" ]]; then
        if [[ -f "$SOURCE_KEYS" ]]; then
             log_info "Initializing keys.env from local config..."
             cp "$SOURCE_KEYS" "$TARGET_KEYS"
             chmod 600 "$TARGET_KEYS"
        elif [[ -f "$TEMPLATE_KEYS" ]]; then
             log_info "Initializing keys.env from template..."
             cp "$TEMPLATE_KEYS" "$TARGET_KEYS"
             chmod 600 "$TARGET_KEYS"
             log_warn "Please edit $TARGET_KEYS to add your API keys."
        fi
    else
        log_info "Existing keys.env found at $TARGET_KEYS, keeping it."
    fi
    
    # Symlink aliases.sh
    # Global: ~/.vibe/aliases.sh -> ~/.vibe/config/aliases.sh
    ln -sf "$INSTALL_DIR/config/aliases.sh" "$INSTALL_DIR/aliases.sh"
    
    VIBE_BIN="$INSTALL_DIR/bin"
    VIBE_HOME_DISPLAY="$INSTALL_DIR"

else
    # Local Installation: Use current directory
    log_step "Initializing Vibe Local Installation in $SOURCE_ROOT"
    
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
    
    VIBE_HOME_DISPLAY="$VIBE_HOME"
fi

# ================= BOOTSTRAP 'vibe' COMMAND =================

log_step "Bootstrapping 'vibe' command"
SHELL_RC=$(get_shell_rc)

RC_CONTENT="# Vibe Coding Control Center
export PATH=\"$VIBE_BIN:\$PATH\"

# Load Vibe aliases
if [ -f \"$VIBE_HOME_DISPLAY/aliases.sh\" ]; then
    source \"$VIBE_HOME_DISPLAY/aliases.sh\"
fi
"

# Clean up old configuration
if grep -Fq "Vibe Coding Control Center" "$SHELL_RC" || grep -Fq "vibe-center" "$SHELL_RC"; then
    log_info "Updating configuration in $SHELL_RC"
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
         sed -i '' '/# Vibe Coding Control Center/d' "$SHELL_RC"
         sed -i '' '/export PATH=".*vibe-center.*\/bin:$PATH"/d' "$SHELL_RC"
         sed -i '' '/export PATH=".*\.vibe\/bin:$PATH"/d' "$SHELL_RC"
         sed -i '' '/source .*\/vibe\/aliases.sh/d' "$SHELL_RC"
         sed -i '' '/# Added by Antigravity/d' "$SHELL_RC"
    else
         sed -i '/# Vibe Coding Control Center/d' "$SHELL_RC"
         sed -i '/export PATH=".*vibe-center.*\/bin:$PATH"/d' "$SHELL_RC"
         sed -i '/export PATH=".*\.vibe\/bin:$PATH"/d' "$SHELL_RC"
         sed -i '/source .*\/vibe\/aliases.sh/d' "$SHELL_RC"
         sed -i '/# Added by Antigravity/d' "$SHELL_RC"
    fi
fi

append_to_rc "$SHELL_RC" "$RC_CONTENT" "Vibe Coding Control Center"

chmod +x "$VIBE_BIN/vibe"
chmod +x "$VIBE_BIN"/* 2>/dev/null || true
log_success "'vibe' command is ready (Mode: $MODE)"

# ================= FINAL SUMMARY =================
log_success "Installation process completed!"

echo -e "\n${BOLD}NEXT STEPS:${NC}"
echo "1. Verify your configuration: ${CYAN}cat $VIBE_HOME_DISPLAY/keys.env${NC}"
echo "2. Reload shell: ${CYAN}source $SHELL_RC${NC} (or restart terminal)"
echo "3. Install AI tools: ${CYAN}vibe equip${NC}"
echo "4. Launch Control Center: ${CYAN}vibe${NC}"
echo "----------------------------------------"
