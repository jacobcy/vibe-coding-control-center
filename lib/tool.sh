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

_tool_require_confirmation() {
    local prompt="$1" assume_yes="${2:-false}"
    local allow_interactive="${VIBE_ALLOW_INTERACTIVE:-}"
    if [[ "$assume_yes" != true && -z "$allow_interactive" ]]; then
        vibe_die "Interactive confirmation disabled for '$prompt'. Rerun with 'vibe tools --yes' or set VIBE_ALLOW_INTERACTIVE=1."
    fi
    local prev_assume="${VIBE_ASSUME_YES:-}" prev_defined=0
    [[ -n "${VIBE_ASSUME_YES+x}" ]] && prev_defined=1
    if [[ "$assume_yes" == true ]]; then
        VIBE_ASSUME_YES=1
    fi
    confirm_action "$prompt"
    local ok=$?
    if [[ "$assume_yes" == true ]]; then
        if [[ "$prev_defined" -eq 1 ]]; then
            VIBE_ASSUME_YES="$prev_assume"
        else
            unset VIBE_ASSUME_YES
        fi
    fi
    return $ok
}

# ── Install Claude ──────────────────────────────────────
_tool_claude() {
    local assume_yes="${1:-false}"
    log_step "Claude Code"
    if vibe_has claude; then
        local ver="$(claude --version 2>&1 | head -1)"
        log_info "Installed: $ver"
        _tool_require_confirmation "Update Claude?" "$assume_yes" || return 0
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
    local assume_yes="${1:-false}"
    log_step "OpenCode"
    if vibe_has opencode; then
        local ver="$(opencode --version 2>&1 | head -1)"
        log_info "Installed: $ver"
        _tool_require_confirmation "Update OpenCode?" "$assume_yes" || return 0
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
    local assume_yes="${1:-false}"
    log_step "Codex"
    if vibe_has codex; then
        local ver="$(codex --version 2>&1 | head -1)"
        log_info "Installed: $ver"
        _tool_require_confirmation "Update Codex?" "$assume_yes" || return 0
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
    echo "Install: ${CYAN}vibe tools <tool>${NC} or ${CYAN}vibe tools all${NC}"
}

# ── Install Core Dependencies ───────────────────────────
_tool_deps() {
    local assume_yes="${1:-false}"
    log_step "Core Dependencies"
    local tools=("git" "jq" "tmux" "lazygit" "curl")
    local missing=()
    for t in "${tools[@]}"; do
        vibe_has "$t" || missing+=("$t")
    done

    if ((${#missing[@]} == 0)); then
        log_success "All core dependencies are present."
        return 0
    fi

    log_warn "Missing: ${missing[*]}"
    if [[ "$OSTYPE" == darwin* ]] && vibe_has brew; then
        if [[ "$assume_yes" != true && -z "${VIBE_ALLOW_INTERACTIVE:-}" ]]; then
            log_info "Pass --yes to install missing tools automatically: ${missing[*]}"
            return 1
        fi
        _tool_require_confirmation "Install missing tools via Homebrew?" "$assume_yes" || return 1
        brew install "${missing[@]}"
    else
        log_info "Please install missing tools manually: ${missing[*]}"
        return 1
    fi
}

# ── Dispatcher ──────────────────────────────────────────
vibe_tool() {
    local assume_yes=false
    [[ "${VIBE_ASSUME_YES:-}" == "1" ]] && assume_yes=true
    local args=()
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -y|--yes)
                assume_yes=true
                shift
                ;;
            *)
                args+=("$1")
                shift
                ;;
        esac
    done
    set -- "${args[@]}"
    local target="${1:-}"

    case "$target" in
        claude)   _tool_claude "$assume_yes" ;;
        opencode) _tool_opencode "$assume_yes" ;;
        codex)    _tool_codex "$assume_yes" ;;
        deps)     _tool_deps "$assume_yes" ;;
        all)
            _tool_deps "$assume_yes"
            _tool_claude "$assume_yes"
            _tool_opencode "$assume_yes"
            _tool_codex "$assume_yes"
            ;;
        ""|status)
            _tool_status
            ;;
        help|-h|--help)
            echo "Usage: ${CYAN}vibe tools <command>${NC}"
            echo ""
            echo "Commands:"
            echo "  ${GREEN}status${NC}    Show installation status of AI tools"
            echo "  ${GREEN}deps${NC}      Install core system dependencies (git, jq, etc.)"
            echo "  ${GREEN}claude${NC}    Install/Update Claude Code"
            echo "  ${GREEN}opencode${NC}  Install/Update OpenCode"
            echo "  ${GREEN}codex${NC}     Install/Update Codex"
            echo "  ${GREEN}all${NC}       Install/Update all tools and dependencies"
            echo ""
            echo "Options:"
            echo "  -y, --yes      Skip confirmation prompts for installs/updates"
            ;;
        *)
            log_error "Unknown tool: $target"
            echo "Run 'vibe tools --help' for usage."
            return 1
            ;;
    esac
}
