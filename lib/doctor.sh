#!/usr/bin/env zsh
# v2/lib/doctor.sh - Environment Diagnostics for Vibe 2.0
# Target: ~200 lines | Detects tools, reports versions
# 支持必要依赖检查(--essential)和完整检查(默认)

# ── Tool Check Tables ────────────────────────────────────
# 必要依赖：vibe运行的核心工具，缺失会导致基本功能不可用
_VIBE_ESSENTIAL_TOOLS=(
    "git:git:--version"
    "uv:uv:--version"
)

# AI开发工具：至少需要其中一个
_VIBE_AI_TOOLS=(
    "claude:claude:--version"
    "opencode:opencode:--version"
    "codex:codex:--version"
)

# 可选依赖：增强体验的工具，缺失不影响核心功能
_VIBE_OPTIONAL_TOOLS=(
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

# ── Check At Least One ───────────────────────────────────
_check_at_least_one() {
    local category="$1"
    shift
    local tools=("$@")
    local found=()

    for entry in "${tools[@]}"; do
        local name="${entry%%:*}"
        local rest="${entry#*:}"
        local cmd="${rest%%:*}"

        if vibe_has "$cmd"; then
            found+=("$name")
        fi
    done

    if [[ ${#found[@]} -gt 0 ]]; then
        printf "  ${GREEN}✓${NC} %-12s %s (at least one required)\n" "$category" "${found[*]}"
        return 0
    else
        printf "  ${RED}✗${NC} %-12s %s (need at least one)\n" "$category" "none found"
        return 1
    fi
}

# ── Essential Check ──────────────────────────────────────
vibe_doctor_essential() {
    local missing=0

    echo "${BOLD}必要依赖检查${NC}"
    echo "$(printf '%.0s─' {1..50})"
    echo ""

    # Core tools
    for entry in "${_VIBE_ESSENTIAL_TOOLS[@]}"; do
        local name="${entry%%:*}"
        local rest="${entry#*:}"
        local cmd="${rest%%:*}"
        local flag="${rest#*:}"
        _check_tool "$name" "$cmd" "$flag" || ((missing+=1))
    done

    # AI tools (at least one)
    _check_at_least_one "AI工具" "${_VIBE_AI_TOOLS[@]}" || ((missing+=1))

    echo ""

    if ((missing == 0)); then
        log_success "所有必要依赖已满足"
        return 0
    else
        log_error "缺少必要依赖，请先安装"
        echo ""
        echo "安装提示："
        echo "  git:  系统包管理器安装"
        echo "  uv:   curl -LsSf https://astral.sh/uv/install.sh | sh"
        echo "  claude: claude.ai 安装"
        echo "  opencode: npm install -g opencode"
        return 1
    fi
}

# ── Full Check (Default) ────────────────────────────────
vibe_doctor() {
    if [[ "$1" == "-h" || "$1" == "--help" ]]; then
        echo "${BOLD}Vibe Environment Doctor${NC}"
        echo ""
        echo "Usage: ${CYAN}vibe doctor${NC} [options]"
        echo ""
        echo "Options:"
        echo "  --essential    只检查必要依赖（git、uv、至少一个AI工具）"
        echo "  --help         显示此帮助信息"
        echo ""
        echo "功能：检测开发环境工具版本、依赖状态及配置完整性。"
        return 0
    fi

    if [[ "$1" == "--essential" ]]; then
        vibe_doctor_essential
        return $?
    fi

    local missing=0
    local optional_missing=0

    echo "${BOLD}Vibe Coding Control Center${NC} — Environment Check"
    echo "$(printf '%.0s─' {1..50})"
    echo ""

    # Vibe version
    echo "${CYAN}Vibe Version:${NC} $(get_vibe_version)"
    echo "${CYAN}VIBE_ROOT:${NC}    $VIBE_ROOT"
    echo ""

    # Essential Tools
    echo "${BOLD}必要依赖:${NC}"
    for entry in "${_VIBE_ESSENTIAL_TOOLS[@]}"; do
        local name="${entry%%:*}"
        local rest="${entry#*:}"
        local cmd="${rest%%:*}"
        local flag="${rest#*:}"
        _check_tool "$name" "$cmd" "$flag" || ((missing+=1))
    done

    # AI tools (at least one)
    _check_at_least_one "AI工具" "${_VIBE_AI_TOOLS[@]}" || ((missing+=1))
    echo ""

    # Optional Tools
    echo "${BOLD}可选依赖:${NC}"
    for entry in "${_VIBE_OPTIONAL_TOOLS[@]}"; do
        local name="${entry%%:*}"
        local rest="${entry#*:}"
        local cmd="${rest%%:*}"
        local flag="${rest#*:}"
        _check_tool "$name" "$cmd" "$flag" || ((optional_missing+=1))
    done
    echo ""

    # Keys status
    echo "${BOLD}API Keys:${NC}"
    [[ -n "$ANTHROPIC_AUTH_TOKEN" ]] && \
        echo "  ${GREEN}✓${NC} ANTHROPIC_AUTH_TOKEN  configured" || \
        echo "  ${YELLOW}!${NC} ANTHROPIC_AUTH_TOKEN  not set"
    [[ -n "$GH_TOKEN" ]] && \
        echo "  ${GREEN}✓${NC} GH_TOKEN              configured" || \
        echo "  ${YELLOW}!${NC} GH_TOKEN              not set"
    [[ -n "$EXA_API_KEY" ]] && \
        echo "  ${GREEN}✓${NC} EXA_API_KEY            configured" || \
        echo "  ${YELLOW}!${NC} EXA_API_KEY            not set"
    [[ -n "$CONTEXT7_API_KEY" ]] && \
        echo "  ${GREEN}✓${NC} CONTEXT7_API_KEY       configured" || \
        echo "  ${YELLOW}!${NC} CONTEXT7_API_KEY       not set"
    echo ""

    # Summary
    if ((missing == 0)); then
        log_success "必要依赖已满足"
        if ((optional_missing > 0)); then
            log_warn "可选依赖缺失 $optional_missing 个（不影响核心功能）"
        fi
    else
        log_error "必要依赖缺失 $missing 个，请先安装"
        echo ""
        echo "Install essential tools first:"
        echo "  ${CYAN}vibe doctor --essential${NC} # 查看必要依赖安装提示"
    fi
}
