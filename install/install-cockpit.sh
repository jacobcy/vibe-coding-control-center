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

# ================= 1. INSTALL COCKPIT TOOLS =================
log_step "1/1 Install/Update Cockpit Tools"

APP_PATH="/Applications/Cockpit Tools.app"

if [[ -d "$APP_PATH" ]]; then
    log_info "Cockpit Tools is already installed."
    
    if confirm_action "Reinstall/Update Cockpit Tools?"; then
        if [[ "$OSTYPE" == "darwin"* ]] && check_command_exists "brew"; then
             log_info "Reinstalling via Homebrew..."
             brew tap jlcodes99/cockpit-tools https://github.com/jlcodes99/cockpit-tools 2>/dev/null || true
             brew install --cask --force cockpit-tools
        else
            log_warn "Manual download required for non-Homebrew setup."
            log_info "Please visit: https://github.com/jlcodes99/cockpit-tools/releases"
        fi
    fi
else
    log_warn "Installing Cockpit Tools..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        if check_command_exists "brew"; then
            brew tap jlcodes99/cockpit-tools https://github.com/jlcodes99/cockpit-tools
            brew install --cask cockpit-tools
            
            # Helper for "Damaged App" issue
            if [[ -d "$APP_PATH" ]]; then
                 log_success "Cockpit Tools installed successfully."
                 echo "💡 If you see 'App is damaged' error, run this fix:"
                 echo "   sudo xattr -rd com.apple.quarantine \"$APP_PATH\""
            fi
        else
             log_critical "Homebrew required for automatic installation." 
             log_info "Please install Homebrew or download manually from: https://github.com/jlcodes99/cockpit-tools/releases"
        fi
    else
        log_warn "This script currently supports macOS Homebrew installation only."
        log_info "For other platforms, visit: https://github.com/jlcodes99/cockpit-tools/releases"
    fi
fi

echo -e "\n${GREEN}Cockpit Tools Installation Check Complete!${NC}"
