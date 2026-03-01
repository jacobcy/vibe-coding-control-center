#!/usr/bin/env zsh
# lib/skills.sh - Skills 管理模块
# 用法: vibe skills [sync|check]
# 对话式审计请使用 /vibe-skills skill

# ─── Main ────────────────────────────────────────────────
vibe_skills() {
    local subcmd="${1:-help}"
    shift 2>/dev/null || true

    case "$subcmd" in
        sync|"")
            # 完整同步
            "$VIBE_ROOT/scripts/sync-skills.sh"
            ;;
        check)
            # 检查状态
            "$VIBE_ROOT/scripts/sync-skills.sh" --check
            ;;
        help|--help|-h)
            _skills_help
            ;;
        *)
            log_error "Unknown subcommand: $subcmd"
            _skills_help
            exit 1
            ;;
    esac
}

_skills_help() {
    echo ""
    echo "${BOLD}vibe skills${NC} - Skills 同步工具"
    echo ""
    echo "用法: ${CYAN}vibe skills${NC} <子命令>"
    echo ""
    echo "子命令:"
    echo "  ${GREEN}sync${NC}     一键同步所有 skills（Claude plugin + 全局 + 本地）"
    echo "  ${GREEN}check${NC}    检查各 Agent skills 状态"
    echo "  ${GREEN}help${NC}     显示此帮助"
    echo ""
    echo "💡 完整审计请使用对话命令: ${CYAN}/vibe-skills${NC}"
    echo ""
    echo "架构:"
    echo "  • Superpowers: 全局 npx skills → Antigravity, Codex, Trae"
    echo "  • Claude Code: claude plugin add superpowers"
    echo "  • 本地 vibe-*: symlink → .agent/, .trae/, .claude/"
    echo ""
}
