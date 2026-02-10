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

# ================= 1. CLONE RESOURCES =================
log_step "1/4 Check Resources"
REPO_URL="https://github.com/affaan-m/everything-claude-code"
PROJECT_PARENT="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_DIR="$PROJECT_PARENT/everything-claude-code"

if [ -d "$PROJECT_DIR" ]; then
    log_info "everything-claude-code exists"
else
    if check_command_exists "git"; then
        git clone "$REPO_URL" "$PROJECT_DIR" 2>/dev/null || {
            log_warn "Clone failed, using local fallback"
            PROJECT_DIR="$SCRIPT_DIR"
        }
    else
        log_warn "git not found, skipping resource clone"
        PROJECT_DIR="$SCRIPT_DIR"
    fi
fi

# ================= 2. INSTALL CLI =================
log_step "2/4 Install/Update Claude CLI"
if command -v claude &> /dev/null; then
    CURRENT_VERSION=$(get_command_version "claude" "--version")
    log_info "Claude CLI already installed${CURRENT_VERSION:+ (version: $CURRENT_VERSION)}"

    if confirm_action "Update Claude CLI to the latest version?"; then
        if [[ "$OSTYPE" == "darwin"* ]] && check_command_exists "brew"; then
            update_via_brew "claude-code"
        elif check_command_exists "npm"; then
            update_via_npm "@anthropic-ai/claude-code"
        else
            log_warn "No supported package manager found for update"
        fi
        NEW_VERSION=$(get_command_version "claude" "--version")
        if [[ -n "$NEW_VERSION" && "$NEW_VERSION" != "$CURRENT_VERSION" ]]; then
            log_success "Updated from $CURRENT_VERSION to $NEW_VERSION"
        fi
    fi
else
    log_warn "Installing Claude CLI..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        check_command_exists "brew" || { log_critical "Homebrew required: https://brew.sh/"; exit 1; }
        brew install claude-code
    else
        check_command_exists "npm" || { log_critical "npm required. Install Node.js first."; exit 1; }
        npm install -g @anthropic-ai/claude-code
    fi
    INSTALLED_VERSION=$(get_command_version "claude" "--version")
    [[ -n "$INSTALLED_VERSION" ]] && log_success "Claude CLI installed (version: $INSTALLED_VERSION)"
fi

# ================= 3. CREATE DIRECTORIES =================
log_step "3/4 Create Directories"
CONFIG_DIRS=("$HOME/.claude/agents" "$HOME/.claude/rules" "$HOME/.claude/commands" "$HOME/.claude/skills")
for dir in "${CONFIG_DIRS[@]}"; do
    mkdir -p "$dir" 2>/dev/null || log_warn "Failed to create: $dir"
done

# ================= 4. COPY ASSETS (optional) =================
log_step "4/4 Copy Assets"
if confirm_action "Copy enhanced configurations (agents, rules, commands, skills) to ~/.claude?"; then
    for asset_dir in "rules" "agents" "commands"; do
        SRC_DIR="$PROJECT_DIR/$asset_dir"
        DEST_DIR="$HOME/.claude/$asset_dir"
        if [[ -d "$SRC_DIR" ]]; then
            mkdir -p "$DEST_DIR" 2>/dev/null
            cp "$SRC_DIR/"*.md "$DEST_DIR/" 2>/dev/null && \
                log_success "Copied $asset_dir to $DEST_DIR" || \
                log_warn "No .md files in $SRC_DIR"
        fi
    done

    SKILLS_SRC="$PROJECT_DIR/skills"
    if [[ -d "$SKILLS_SRC" ]]; then
        mkdir -p "$HOME/.claude/skills" 2>/dev/null
        cp -r "$SKILLS_SRC/"* "$HOME/.claude/skills/" 2>/dev/null && \
            log_success "Copied skills" || \
            log_warn "Failed to copy skills"
    fi
fi

echo -e "\n${GREEN}Claude Code Installation Complete!${NC}"
echo "Next: Run 'vibe env setup' to configure API keys and MCP servers."
