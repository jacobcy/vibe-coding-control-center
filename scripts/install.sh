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

# ================= INSTALLATION =================

log_step "Running Claude Code Installer"
zsh "$SCRIPT_DIR/../install/install-claude.sh"

log_step "Running OpenCode Installer"
zsh "$SCRIPT_DIR/../install/install-opencode.sh"

# ================= FINAL SUMMARY =================
log_success "Installation process completed!"

echo -e "\n${BOLD}NEXT STEPS:${NC}"
echo "1. Run: source $SHELL_RC"
echo "2. Edit config/keys.env if you haven't already."
echo "3. Use 'vibe' to start the control center."
echo "----------------------------------------"
