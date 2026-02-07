#!/usr/bin/env zsh
# OpenCode Installation Script
# Refactored for Security & Modularity

if [ -z "${ZSH_VERSION:-}" ]; then
    if command -v zsh >/dev/null 2>&1; then
        exec zsh -l "$0" "$@"
    fi
    echo "zsh not found. Please run ./scripts/install.sh to install zsh." >&2
    exit 1
fi

set -e

# ================= SETUP =================
SCRIPT_DIR="$(cd "$(dirname "${(%):-%x}")" && pwd)"
source "$SCRIPT_DIR/../lib/utils.sh"

log_step "1/4 Check & Update OpenCode CLI"
if command -v opencode &> /dev/null; then
    # Get current version
    CURRENT_VERSION=$(get_command_version "opencode" "--version")

    if [[ -n "$CURRENT_VERSION" ]]; then
        log_info "OpenCode CLI already installed (version: $CURRENT_VERSION)"
    else
        log_info "OpenCode CLI already installed (version: unknown)"
    fi

    # Ask if user wants to update
    if confirm_action "Do you want to update OpenCode CLI to the latest version?"; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            if ! check_command_exists "brew"; then
                log_warn "Homebrew not found. Skipping update."
            else
                update_via_brew "opencode"

                # Show new version
                NEW_VERSION=$(get_command_version "opencode" "--version")
                if [[ -n "$NEW_VERSION" && "$NEW_VERSION" != "$CURRENT_VERSION" ]]; then
                    log_success "Updated from $CURRENT_VERSION to $NEW_VERSION"
                fi
            fi
        else
            log_warn "Updating OpenCode on non-macOS systems..."
            curl -fsSL https://raw.githubusercontent.com/omo-ai/opencode/main/install.sh | bash

            # Show new version
            NEW_VERSION=$(get_command_version "opencode" "--version")
            if [[ -n "$NEW_VERSION" && "$NEW_VERSION" != "$CURRENT_VERSION" ]]; then
                log_success "Updated from $CURRENT_VERSION to $NEW_VERSION"
            fi
        fi
    else
        log_info "Skipping OpenCode CLI update"
    fi
else
    log_warn "Installing OpenCode CLI..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        if ! check_command_exists "brew"; then
            log_critical "Homebrew not found. Please install Homebrew first: https://brew.sh/"
            exit 1
        fi
        brew tap omo-ai/opencode
        brew install opencode
    else
        curl -fsSL https://raw.githubusercontent.com/omo-ai/opencode/main/install.sh | bash
    fi

    # Show installed version
    INSTALLED_VERSION=$(get_command_version "opencode" "--version")
    if [[ -n "$INSTALLED_VERSION" ]]; then
        log_success "OpenCode CLI installed (version: $INSTALLED_VERSION)"
    fi
fi

# ================= SECRETS & ENV =================
log_step "2/4 Configure Environment & Secrets"
KEYS_FILE="$SCRIPT_DIR/../config/keys.env"

if [ ! -f "$KEYS_FILE" ]; then
    log_warn "Secrets file not found! Please run install-claude.sh first or create config/keys.env"
    exit 1
fi

set -a
source "$KEYS_FILE"
set +a

SHELL_RC=$(get_shell_rc)
RC_CONTENT="
# OpenCode Configuration (optional - OpenCode works natively with multiple models)
export DEEPSEEK_API_KEY=\"\${DEEPSEEK_API_KEY}\"
export MOONSHOT_API_KEY=\"\${MOONSHOT_API_KEY}\"
"
append_to_rc "$SHELL_RC" "$RC_CONTENT" "OpenCode Configuration"

# ================= EXTENSIONS =================
log_step "3/4 Check & Install oh-my-opencode"
if [ -d "$HOME/.oh-my-opencode" ]; then
    log_info "oh-my-opencode already installed"

    if confirm_action "Do you want to update oh-my-opencode?"; then
        log_info "Updating oh-my-opencode..."
        (cd "$HOME/.oh-my-opencode" && git pull origin main 2>/dev/null)

        if [ -f "$HOME/.oh-my-opencode/install.sh" ]; then
            (cd "$HOME/.oh-my-opencode" && bash install.sh)
            log_success "oh-my-opencode updated"
        fi
    else
        log_info "Skipping oh-my-opencode update"
    fi
else
    log_warn "Installing oh-my-opencode..."

    if ! check_command_exists "git"; then
        log_warn "git not found. Skipping oh-my-opencode installation."
    else
        if git clone https://github.com/oh-my-opencode/oh-my-opencode.git "$HOME/.oh-my-opencode" 2>/dev/null; then
            if [ -f "$HOME/.oh-my-opencode/install.sh" ]; then
                (cd "$HOME/.oh-my-opencode" && bash install.sh)
                log_success "oh-my-opencode installed"
            fi
        else
            log_warn "Failed to clone oh-my-opencode repository"
        fi
    fi
fi

# ================= OPENCODE CONFIG =================
log_step "4/4 Create OpenCode Config Directory"
mkdir -p "$HOME/.opencode"
log_info "OpenCode config directory ready"

echo -e "\n${GREEN}OpenCode Installation Complete!${NC}"
