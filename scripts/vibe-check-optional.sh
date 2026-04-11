#!/usr/bin/env zsh
# scripts/vibe-check-optional.sh - 可选依赖检查和安装引导
# 用于vibe-onboard skill调用，或用户手动运行检查可选组件

set -euo pipefail

VIBE_ROOT="$(cd "$(dirname "${(%):-%x}")/.." && pwd)"
[[ -f "$VIBE_ROOT/lib/utils.sh" ]] && source "$VIBE_ROOT/lib/utils.sh"
[[ -f "$VIBE_ROOT/lib/config.sh" ]] && source "$VIBE_ROOT/lib/config.sh"

# ── Helper Functions ─────────────────────────────────────
_check_optional_tool() {
    local name="$1" cmd="$2" install_hint="$3"

    if command -v "$cmd" >/dev/null 2>&1; then
        local version="$("$cmd" --version 2>&1 | head -1 | sed 's/^[^0-9]*//')"
        printf "  ${GREEN}✓${NC} %-15s %s\n" "$name" "${version:-installed}"
        return 0
    else
        printf "  ${YELLOW}!${NC} %-15s %s\n" "$name" "未安装"
        echo "      安装: $install_hint"
        return 1
    fi
}

# ── Remote Development Tools ─────────────────────────────
check_remote_dev_tools() {
    echo "${BOLD}远程开发工具:${NC}"
    echo ""

    _check_optional_tool "tailscale" "tailscale" "brew install tailscale"
    _check_optional_tool "ncat" "ncat" "brew install nmap"
    _check_optional_tool "tsu.sh" "tsu" "ln -sf ~/scripts/tsu.sh ~/.local/bin/tsu"

    # SSH Agent check
    if ssh-add -l >/dev/null 2>&1; then
        printf "  ${GREEN}✓${NC} %-15s running\n" "ssh-agent"
    else
        printf "  ${YELLOW}!${NC} %-15s 未运行\n" "ssh-agent"
        echo "      启动: eval \"$(ssh-agent -s)\" && ssh-add ~/.ssh/id_ed25519"
    fi
    echo ""
}

# ── AI Backend Extensions ───────────────────────────────
check_ai_backends() {
    echo "${BOLD}AI后端扩展:${NC}"
    echo ""

    _check_optional_tool "gemini CLI" "gemini" "npm install -g @google/gemini-cli"

    # MCP check (check Python package)
    if python3 -c "import mcp" 2>/dev/null; then
        printf "  ${GREEN}✓${NC} %-15s installed\n" "mcp"
    else
        printf "  ${YELLOW}!${NC} %-15s 未安装\n" "mcp"
        echo "      安装: cd $VIBE_ROOT && uv sync --extra mcp"
    fi
    echo ""
}

# ── Development Helpers ─────────────────────────────────
check_dev_helpers() {
    echo "${BOLD}开发辅助工具:${NC}"
    echo ""

    _check_optional_tool "direnv" "direnv" "brew install direnv"
    _check_optional_tool "pre-commit" "pre-commit" "pip install pre-commit 或 uv pip install pre-commit"
    _check_optional_tool "supervisor" "supervisord" "brew install supervisor"
    echo ""
}

# ── Main Function ───────────────────────────────────────
vibe_check_optional() {
    local category="${1:-all}"

    case "$category" in
        remote)
            check_remote_dev_tools
            ;;
        ai)
            check_ai_backends
            ;;
        helpers)
            check_dev_helpers
            ;;
        all|"")
            check_remote_dev_tools
            check_ai_backends
            check_dev_helpers
            ;;
        *)
            echo "用法: vibe-check-optional [remote|ai|helpers|all]"
            return 1
            ;;
    esac

    echo "${BOLD}提示:${NC} 这些都是可选组件，不影响Vibe核心功能。"
    echo "根据你的开发需求选择性安装即可。"
}

# ── Entry Point ────────────────────────────────────────
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "${BOLD}Vibe可选依赖检查工具${NC}"
    echo ""
    echo "Usage: ${CYAN}vibe-check-optional${NC} [category]"
    echo ""
    echo "Categories:"
    echo "  remote    远程开发工具（tailscale、ncat、ssh-agent等）"
    echo "  ai        AI后端扩展（gemini CLI、mcp等）"
    echo "  helpers   开发辅助工具（direnv、pre-commit、supervisor等）"
    echo "  all       检查所有可选组件（默认）"
    echo ""
    echo "这些组件都是可选的，根据你的实际需求选择性安装。"
else
    vibe_check_optional "${1:-all}"
fi