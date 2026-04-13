#!/usr/bin/env zsh
# scripts/vibe-check-tools.sh - AI开发工具状态检查
# 只检查工具状态，不执行安装。安装引导由 /vibe-onboard skill 负责。

set -euo pipefail

VIBE_ROOT="$(cd "$(dirname "${(%):-%x}")/.." && pwd)"
[[ -f "$VIBE_ROOT/lib/utils.sh" ]] && source "$VIBE_ROOT/lib/utils.sh"
[[ -f "$VIBE_ROOT/lib/config.sh" ]] && source "$VIBE_ROOT/lib/config.sh"

# ── Helper Functions ─────────────────────────────────────
_check_tool_status() {
    local name="$1" cmd="$2"

    if command -v "$cmd" >/dev/null 2>&1; then
        local version="$($cmd --version 2>&1 | head -1 | sed 's/^[^0-9]*//')"
        printf "  ${GREEN}✓${NC} %-12s %s\n" "$name" "${version:-installed}"
        return 0
    else
        printf "  ${YELLOW}○${NC} %-12s 未安装\n" "$name"
        return 1
    fi
}

# ── AI Tools Status Check ────────────────────────────────
check_ai_tools() {
    echo "${BOLD}AI 开发工具状态:${NC}"
    echo ""

    local tools=("claude" "opencode" "codex")
    local installed=0

    for tool in "${tools[@]}"; do
        if _check_tool_status "$tool" "$tool"; then
            ((installed+=1))
        fi
    done

    echo ""

    if ((installed == 0)); then
        log_error "未安装任何 AI 工具，Vibe 无法正常工作"
        echo ""
        echo "至少需要安装其中一个："
        echo "  - ${CYAN}claude${NC}  : Anthropic 官方工具（付费，功能强大）"
        echo "  - ${CYAN}opencode${NC} : 开源免费工具（推荐尝鲜）"
        echo ""
        echo "安装引导：${CYAN}/vibe-onboard${NC}"
        return 1
    elif ((installed == 1)); then
        log_success "1 个 AI 工具可用，Vibe 可以正常使用"
        echo ""
        echo "可继续安装其他工具：${CYAN}/vibe-onboard${NC}"
    else
        log_success "$installed 个 AI 工具可用，Vibe 可以正常使用"
    fi
}

# ── Installation Hints (No Execution) ────────────────────
show_install_hints() {
    echo ""
    echo "${BOLD}安装提示:${NC}"
    echo ""

    if ! command -v "claude" >/dev/null 2>&1; then
        echo "Claude Code:"
        echo "  - 官网：${CYAN}claude.ai${NC}"
        echo "  - Homebrew: ${CYAN}brew install claude${NC} (如果可用)"
        echo "  - 需要：ANTHROPIC_AUTH_TOKEN"
        echo ""
    fi

    if ! command -v "opencode" >/dev/null 2>&1; then
        echo "OpenCode:"
        echo "  - 安装：${CYAN}npm install -g opencode${NC}"
        echo "  - 需要：npm (Node.js)"
        echo "  - 免费：支持 Kimi、DeepSeek 等免费模型"
        echo ""
    fi

    echo "完整引导：${CYAN}/vibe-onboard${NC}"
}

# ── Main Function ───────────────────────────────────────
vibe_check_tools() {
    local show_hints="${1:-}"

    check_ai_tools

    if [[ "$show_hints" == "--hints" ]] || ! command -v "claude" >/dev/null 2>&1 || ! command -v "opencode" >/dev/null 2>&1; then
        show_install_hints
    fi
}

# ── Entry Point ────────────────────────────────────────
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "${BOLD}vibe-check-tools - AI开发工具状态检查${NC}"
    echo ""
    echo "Usage: ${CYAN}vibe-check-tools${NC} [options]"
    echo ""
    echo "Options:"
    echo "  --hints    显示安装提示"
    echo "  -h, --help 显示帮助信息"
    echo ""
    echo "此脚本只检查工具状态，不执行安装。"
    echo "安装引导请使用：${CYAN}/vibe-onboard${NC}"
else
    vibe_check_tools "${1:-}"
fi