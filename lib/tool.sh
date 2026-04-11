#!/usr/bin/env zsh
# v2/lib/tool.sh - Tool Status Check for Vibe 2.0
# 只负责检查工具状态，安装操作由 scripts/vibe-install-tools.sh 或 vibe-onboard skill 处理

# ── Status Report ───────────────────────────────────────
vibe_tool() {
    local target="${1:-status}"

    case "$target" in
        ""|status)
            echo "${BOLD}AI Tool Status${NC}"
            echo ""
            local tools=("claude:claude" "opencode:opencode" "codex:codex")
            local installed=0
            for entry in "${tools[@]}"; do
                local name="${entry%%:*}" cmd="${entry#*:}"
                if vibe_has "$cmd"; then
                    local ver="$("$cmd" --version 2>&1 | head -1)"
                    printf "  ${GREEN}✓${NC} %-12s %s\n" "$name" "$ver"
                    ((installed+=1))
                else
                    printf "  ${RED}✗${NC} %-12s %s\n" "$name" "not installed"
                fi
            done
            echo ""

            if ((installed == 0)); then
                log_warn "No AI tools installed"
                echo "至少需要一个AI工具才能使用Vibe"
                echo ""
                echo "安装引导："
                echo "  ${CYAN}/vibe-onboard${NC}         交互式安装引导（推荐）"
                echo "  ${CYAN}vibe-install-tools.sh${NC}  脚本自动安装"
            elif ((installed < ${#tools[@]})); then
                log_info "$installed/${#tools[@]} AI tools installed"
                echo "已安装的AI工具可以正常使用Vibe"
            else
                log_success "All AI tools available"
            fi
            ;;
        help|-h|--help)
            echo "${BOLD}vibe tools - AI工具状态检查${NC}"
            echo ""
            echo "Usage: ${CYAN}vibe tools${NC}"
            echo ""
            echo "功能：检查AI开发工具的安装状态"
            echo ""
            echo "检查的工具："
            echo "  - claude (Claude Code)"
            echo "  - opencode (OpenCode)"
            echo "  - codex (Codex)"
            echo ""
            echo "安装工具："
            echo "  ${CYAN}/vibe-onboard${NC}         交互式安装引导（推荐）"
            echo "  ${CYAN}vibe-install-tools.sh${NC}  脚本自动安装"
            ;;
        *)
            log_error "vibe tools 只负责检查状态，不执行安装"
            echo ""
            echo "安装工具请使用："
            echo "  ${CYAN}/vibe-onboard${NC}         交互式安装引导（推荐）"
            echo "  ${CYAN}vibe-install-tools.sh${NC}  脚本自动安装"
            echo ""
            echo "查看帮助：vibe tools --help"
            return 1
            ;;
    esac
}
