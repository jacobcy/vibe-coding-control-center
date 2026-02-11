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

log_step "Starting Vibe Coding Control Center Installation"
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

# ================= INITIALIZE ~/.vibe/ =================

log_step "Initializing Vibe configuration directory"
VIBE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VIBE_BIN="$VIBE_ROOT/bin"
VIBE_HOME="$VIBE_ROOT/.vibe"

# Sync project configuration to user directory
if ! sync_keys_env "$VIBE_ROOT"; then
    log_error "Installation requires a configured keys.env"
    log_info "Please create $VIBE_ROOT/config/keys.env and run install again"
    exit 1
fi



# Create symlink to aliases.sh instead of copying
ALIASES_LINK="$VIBE_HOME/aliases.sh"
ALIASES_TARGET="$VIBE_ROOT/config/aliases.sh"

if [[ -e "$ALIASES_LINK" || -L "$ALIASES_LINK" ]]; then
    # Remove existing file or symlink
    rm -f "$ALIASES_LINK"
    log_info "Removed existing aliases.sh"
fi

# Create new symlink
ln -s "$ALIASES_TARGET" "$ALIASES_LINK"
log_success "Created aliases.sh symlink -> $ALIASES_TARGET"

# ================= BOOTSTRAP 'vibe' COMMAND =================

log_step "Bootstrapping 'vibe' command"
SHELL_RC=$(get_shell_rc)

RC_CONTENT="# Vibe Coding Control Center
export PATH=\"$VIBE_BIN:\$PATH\"

# Load Vibe aliases (aliases.sh auto-detects VIBE_ROOT from its own path)
if [ -f \"$VIBE_HOME/aliases.sh\" ]; then
    source \"$VIBE_HOME/aliases.sh\"
fi
"

append_to_rc "$SHELL_RC" "$RC_CONTENT" "Vibe Coding Control Center"

chmod +x "$VIBE_BIN/vibe"
chmod +x "$VIBE_BIN"/* 2>/dev/null || true
log_success "'vibe' command is ready"

# ================= FINAL SUMMARY =================
log_success "Installation process completed!"

echo -e "\n${BOLD}NEXT STEPS:${NC}"
echo "1. Verify your configuration: ${CYAN}cat $VIBE_HOME/keys.env${NC}"
echo "2. Reload shell: ${CYAN}source $SHELL_RC${NC} (or restart terminal)"
echo "3. Install AI tools: ${CYAN}vibe equip${NC}"
echo "4. Launch Control Center: ${CYAN}vibe${NC}"
echo "----------------------------------------"
