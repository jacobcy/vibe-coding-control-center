#!/usr/bin/env zsh
# v2/lib/tool.sh - Tool Installation for Vibe 2.0
# Target: ~120 lines | Install/update claude, opencode, codex

# ── Install Helpers ─────────────────────────────────────
_tool_install_via_brew() {
    local pkg="$1"
    vibe_has brew || { log_error "Homebrew required: https://brew.sh/"; return 1; }
    brew install "$pkg"
}

_tool_install_via_npm() {
    local pkg="$1"
    vibe_has npm || { log_error "npm required: https://nodejs.org/"; return 1; }
    npm install -g "$pkg"
}

_tool_update_via_brew() {
    local pkg="$1"
    vibe_has brew && brew upgrade "$pkg" 2>/dev/null
}

# ── Install Claude ──────────────────────────────────────
_tool_claude() {
    log_step "Claude Code"
    if vibe_has claude; then
        local ver="$(claude --version 2>&1 | head -1)"
        log_info "Installed: $ver"
        confirm_action "Update Claude?" || return 0
        if [[ "$OSTYPE" == darwin* ]] && vibe_has brew; then
            _tool_update_via_brew "claude-code"
        elif vibe_has npm; then
            _tool_install_via_npm "@anthropic-ai/claude-code"
        fi
    else
        log_warn "Not installed. Installing..."
        if [[ "$OSTYPE" == darwin* ]]; then
            _tool_install_via_brew "claude-code"
        else
            _tool_install_via_npm "@anthropic-ai/claude-code"
        fi
    fi
    vibe_has claude && log_success "Claude: $(claude --version 2>&1 | head -1)"
}

# ── Install OpenCode ────────────────────────────────────
_tool_opencode() {
    log_step "OpenCode"
    if vibe_has opencode; then
        local ver="$(opencode --version 2>&1 | head -1)"
        log_info "Installed: $ver"
        confirm_action "Update OpenCode?" || return 0
        if [[ "$OSTYPE" == darwin* ]] && vibe_has brew; then
            _tool_update_via_brew "opencode"
        else
            curl -fsSL https://raw.githubusercontent.com/omo-ai/opencode/main/install.sh | bash
        fi
    else
        log_warn "Not installed. Installing..."
        if [[ "$OSTYPE" == darwin* ]] && vibe_has brew; then
            vibe_has brew && brew tap omo-ai/opencode 2>/dev/null
            _tool_install_via_brew "opencode"
        else
            curl -fsSL https://raw.githubusercontent.com/omo-ai/opencode/main/install.sh | bash
        fi
    fi
    vibe_has opencode && log_success "OpenCode: $(opencode --version 2>&1 | head -1)"
}

# ── Install Codex ───────────────────────────────────────
_tool_codex() {
    log_step "Codex"
    if vibe_has codex; then
        local ver="$(codex --version 2>&1 | head -1)"
        log_info "Installed: $ver"
        confirm_action "Update Codex?" || return 0
        _tool_install_via_npm "@openai/codex"
    else
        log_warn "Not installed. Installing..."
        _tool_install_via_npm "@openai/codex"
    fi
    vibe_has codex && log_success "Codex: $(codex --version 2>&1 | head -1)"
}

# ── Status Report ───────────────────────────────────────
_tool_status() {
    echo "${BOLD}AI Tool Status${NC}"
    echo ""
    local tools=("claude:claude" "opencode:opencode" "codex:codex")
    for entry in "${tools[@]}"; do
        local name="${entry%%:*}" cmd="${entry#*:}"
        if vibe_has "$cmd"; then
            local ver="$("$cmd" --version 2>&1 | head -1)"
            printf "  ${GREEN}✓${NC} %-12s %s\n" "$name" "$ver"
        else
            printf "  ${RED}✗${NC} %-12s %s\n" "$name" "not installed"
        fi
    done
    echo ""
    echo "💡 Install: ${CYAN}vibe tool <tool>${NC} or ${CYAN}vibe tool all${NC}"
}

# ── Dispatcher ──────────────────────────────────────────
vibe_tool() {
    local target="${1:-}"

    case "$target" in
        claude)   _tool_claude ;;
        opencode) _tool_opencode ;;
        codex)    _tool_codex ;;
        all)
            _tool_claude
            _tool_opencode
            _tool_codex
            ;;
        ""|status)
            _tool_status
            ;;
        *)
            log_error "Unknown tool: $target"
            echo "Usage: vibe tool {claude|opencode|codex|all|status}"
            ;;
    esac
}
