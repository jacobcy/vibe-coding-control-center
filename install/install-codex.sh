#!/usr/bin/env zsh

if [ -z "${ZSH_VERSION:-}" ]; then
    if command -v zsh >/dev/null 2>&1; then
        exec zsh -l "$0" "$@"
    fi
    echo "zsh not found. Please run ./scripts/install.sh first." >&2
    exit 1
fi

set -e

SCRIPT_DIR="$(cd "$(dirname "${(%):-%x}")" && pwd)"
source "$SCRIPT_DIR/../lib/utils.sh"

# ================= 1. INSTALL CODEX CLI =================
log_step "1/1 Install/Update Codex CLI"

if command -v codex &> /dev/null; then
    CURRENT_VERSION=$(get_command_version "codex" "--version")
    log_info "Codex CLI already installed${CURRENT_VERSION:+ (version: $CURRENT_VERSION)}"

    if confirm_action "Update Codex CLI to the latest version?"; then
        if check_command_exists "npm"; then
            log_info "Updating via npm..."
            npm install -g @openai/codex
        else
            log_warn "npm not found. Cannot update automatically."
        fi
        
        NEW_VERSION=$(get_command_version "codex" "--version")
        if [[ -n "$NEW_VERSION" && "$NEW_VERSION" != "$CURRENT_VERSION" ]]; then
             log_success "Updated from $CURRENT_VERSION to $NEW_VERSION"
        fi
    fi
else
    log_warn "Installing Codex CLI..."
    if check_command_exists "npm"; then
        log_info "Installing via npm (@openai/codex)..."
        npm install -g @openai/codex
        
        if command -v codex &> /dev/null; then
            INSTALLED_VERSION=$(get_command_version "codex" "--version")
            log_success "Codex CLI installed (version: $INSTALLED_VERSION)"
        else
            log_error "Installation failed or 'codex' is not in PATH."
        fi
    else
        log_warn "npm is required to install Codex CLI."
        log_info "Please install Node.js/npm first: https://nodejs.org/"
    fi
fi

echo -e "\n${GREEN}Codex Installation Check Complete!${NC}"
