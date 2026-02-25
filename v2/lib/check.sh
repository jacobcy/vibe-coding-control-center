#!/usr/bin/env zsh
# v2/lib/check.sh - Environment Diagnostics for Vibe 2.0
# Target: ~80 lines | Detects tools, reports versions

# ── Tool Check Table ────────────────────────────────────
# Each entry: name, check_command, version_flag
_VIBE_TOOLS=(
    "claude:claude:--version"
    "opencode:opencode:--version"
    "codex:codex:--version"
    "git:git:--version"
    "gh:gh:--version"
    "tmux:tmux:-V"
    "jq:jq:--version"
    "lazygit:lazygit:--version"
    "node:node:--version"
    "npm:npm:--version"
)

# ── Check Single Tool ───────────────────────────────────
_check_tool() {
    local name="$1" cmd="$2" flag="$3"
    local version=""

    if vibe_has "$cmd"; then
        version="$("$cmd" "$flag" 2>&1 | head -1 | sed 's/^[^0-9]*//')"
        printf "  ${GREEN}✓${NC} %-12s %s\n" "$name" "${version:-installed}"
        return 0
    else
        printf "  ${RED}✗${NC} %-12s %s\n" "$name" "not found"
        return 1
    fi
}

# ── Main Check ──────────────────────────────────────────
vibe_check() {
    local missing=0
    local total=${#_VIBE_TOOLS[@]}

    echo "${BOLD}Vibe Coding Control Center${NC} — Environment Check"
    echo "$(printf '%.0s─' {1..50})"
    echo ""

    # Vibe version
    echo "${CYAN}Vibe Version:${NC} $(get_vibe_version)"
    echo "${CYAN}VIBE_ROOT:${NC}    $VIBE_ROOT"
    echo ""

    # Tools
    echo "${BOLD}Tools:${NC}"
    for entry in "${_VIBE_TOOLS[@]}"; do
        local name="${entry%%:*}"
        local rest="${entry#*:}"
        local cmd="${rest%%:*}"
        local flag="${rest#*:}"
        _check_tool "$name" "$cmd" "$flag" || ((missing++))
    done
    echo ""

    # Keys status
    echo "${BOLD}API Keys:${NC}"
    [[ -n "$ANTHROPIC_AUTH_TOKEN" ]] && \
        echo "  ${GREEN}✓${NC} ANTHROPIC_AUTH_TOKEN  configured" || \
        echo "  ${YELLOW}!${NC} ANTHROPIC_AUTH_TOKEN  not set"
    [[ -n "$GITHUB_PERSONAL_ACCESS_TOKEN" ]] && \
        echo "  ${GREEN}✓${NC} GITHUB_TOKEN          configured" || \
        echo "  ${YELLOW}!${NC} GITHUB_TOKEN          not set"
    [[ -n "$BRAVE_API_KEY" ]] && \
        echo "  ${GREEN}✓${NC} BRAVE_API_KEY         configured" || \
        echo "  ${YELLOW}!${NC} BRAVE_API_KEY         not set"
    echo ""

    # Summary
    local found=$((total - missing))
    if ((missing == 0)); then
        log_success "All $total tools detected"
    else
        log_warn "$found/$total tools found ($missing missing)"
        echo ""
        echo "💡 Install missing tools: ${CYAN}vibe equip${NC}"
    fi
}
