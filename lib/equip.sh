#!/usr/bin/env zsh
# v2/lib/equip.sh - Tool Installation for Vibe 2.0
# Target: ~120 lines | Install/update claude, opencode, codex

# ── Install Helpers ─────────────────────────────────────
_equip_install_via_brew() {
    local pkg="$1"
    vibe_has brew || { log_error "Homebrew required: https://brew.sh/"; return 1; }
    brew install "$pkg"
}

_equip_install_via_npm() {
    local pkg="$1"
    vibe_has npm || { log_error "npm required: https://nodejs.org/"; return 1; }
    npm install -g "$pkg"
}

_equip_update_via_brew() {
    local pkg="$1"
    vibe_has brew && brew upgrade "$pkg" 2>/dev/null
}

# ── Install Claude ──────────────────────────────────────
_equip_claude() {
    log_step "Claude Code"
    if vibe_has claude; then
        local ver="$(claude --version 2>&1 | head -1)"
        log_info "Installed: $ver"
        confirm_action "Update Claude?" || return 0
        if [[ "$OSTYPE" == darwin* ]] && vibe_has brew; then
            _equip_update_via_brew "claude-code"
        elif vibe_has npm; then
            _equip_install_via_npm "@anthropic-ai/claude-code"
        fi
    else
        log_warn "Not installed. Installing..."
        if [[ "$OSTYPE" == darwin* ]]; then
            _equip_install_via_brew "claude-code"
        else
            _equip_install_via_npm "@anthropic-ai/claude-code"
        fi
    fi
    vibe_has claude && log_success "Claude: $(claude --version 2>&1 | head -1)"
}

# ── Install OpenCode ────────────────────────────────────
_equip_opencode() {
    log_step "OpenCode"
    if vibe_has opencode; then
        local ver="$(opencode --version 2>&1 | head -1)"
        log_info "Installed: $ver"
        confirm_action "Update OpenCode?" || return 0
        if [[ "$OSTYPE" == darwin* ]] && vibe_has brew; then
            _equip_update_via_brew "opencode"
        else
            curl -fsSL https://raw.githubusercontent.com/omo-ai/opencode/main/install.sh | bash
        fi
    else
        log_warn "Not installed. Installing..."
        if [[ "$OSTYPE" == darwin* ]] && vibe_has brew; then
            vibe_has brew && brew tap omo-ai/opencode 2>/dev/null
            _equip_install_via_brew "opencode"
        else
            curl -fsSL https://raw.githubusercontent.com/omo-ai/opencode/main/install.sh | bash
        fi
    fi
    vibe_has opencode && log_success "OpenCode: $(opencode --version 2>&1 | head -1)"
}

# ── Install Codex ───────────────────────────────────────
_equip_codex() {
    log_step "Codex"
    if vibe_has codex; then
        local ver="$(codex --version 2>&1 | head -1)"
        log_info "Installed: $ver"
        confirm_action "Update Codex?" || return 0
        _equip_install_via_npm "@openai/codex"
    else
        log_warn "Not installed. Installing..."
        _equip_install_via_npm "@openai/codex"
    fi
    vibe_has codex && log_success "Codex: $(codex --version 2>&1 | head -1)"
}

# ── Status Report ───────────────────────────────────────
_equip_status() {
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
    echo "💡 Install: ${CYAN}vibe equip <tool>${NC} or ${CYAN}vibe equip all${NC}"
}

# ── Dispatcher ──────────────────────────────────────────
vibe_equip() {
    local target="${1:-}"

    case "$target" in
        claude)   _equip_claude ;;
        opencode) _equip_opencode ;;
        codex)    _equip_codex ;;
        all)
            _equip_claude
            _equip_opencode
            _equip_codex
            ;;
        ""|status)
            _equip_status
            ;;
        *)
            log_error "Unknown tool: $target"
            echo "Usage: vibe equip {claude|opencode|codex|all|status}"
            ;;
    esac
}
