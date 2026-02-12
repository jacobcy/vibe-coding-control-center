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

# ================= 1. INSTALL CLI =================
log_step "1/3 Install/Update OpenCode CLI"
if command -v opencode &> /dev/null; then
    CURRENT_VERSION=$(get_command_version "opencode" "--version")
    log_info "OpenCode CLI already installed${CURRENT_VERSION:+ (version: $CURRENT_VERSION)}"

    if confirm_action "Update OpenCode CLI to the latest version?"; then
        if [[ "$OSTYPE" == "darwin"* ]] && check_command_exists "brew"; then
            update_via_brew "opencode"
        else
            curl -fsSL https://raw.githubusercontent.com/omo-ai/opencode/main/install.sh | bash
        fi
        NEW_VERSION=$(get_command_version "opencode" "--version")
        if [[ -n "$NEW_VERSION" && "$NEW_VERSION" != "$CURRENT_VERSION" ]]; then
            log_success "Updated from $CURRENT_VERSION to $NEW_VERSION"
        fi
    fi
else
    log_warn "Installing OpenCode CLI..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        check_command_exists "brew" || { log_critical "Homebrew required: https://brew.sh/"; exit 1; }
        brew tap omo-ai/opencode
        brew install opencode
    else
        curl -fsSL https://raw.githubusercontent.com/omo-ai/opencode/main/install.sh | bash
    fi
    INSTALLED_VERSION=$(get_command_version "opencode" "--version")
    [[ -n "$INSTALLED_VERSION" ]] && log_success "OpenCode CLI installed (version: $INSTALLED_VERSION)"
fi

# ================= 2. INSTALL EXTENSIONS =================
log_step "2/3 Check oh-my-opencode"
if [[ -f "$HOME/.config/opencode/opencode.json" ]] && grep -q "oh-my-opencode" "$HOME/.config/opencode/opencode.json"; then
    log_info "oh-my-opencode already installed (detected in opencode.json)"
    if confirm_action "Update oh-my-opencode?"; then
        if check_command_exists "bun"; then
            bunx oh-my-opencode install
        else
            log_warn "bun not found. Cannot update oh-my-opencode."
        fi
    fi
else
    if check_command_exists "bun"; then
        if confirm_action "Install oh-my-opencode extension (via bunx)?"; then
            log_info "Running bunx oh-my-opencode install..."
            bunx oh-my-opencode install
        fi
    else
        log_warn "bun not found. Skipping oh-my-opencode installation."
        log_info "Please install bun first: https://bun.sh/"
    fi
fi

# ================= 3. CREATE CONFIG DIR =================
log_step "3/3 Create Config Directory"
mkdir -p "$HOME/.opencode" "$HOME/.config/opencode" 2>/dev/null || true
log_info "OpenCode config directories ready"

echo -e "\n${GREEN}OpenCode Installation Complete!${NC}"
echo "Next: Configure your keys in ~/.config/opencode/opencode.json"
echo "  → Run 'vibe config opencode edit' or edit the file manually."
