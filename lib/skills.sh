#!/usr/bin/env zsh
# lib/skills.sh - Skills CLI dispatcher

if [[ "${VIBE_SKILLS_SYNC_LOADED:-}" != "$VIBE_LIB/skills_sync.sh" ]]; then
    source "$VIBE_LIB/skills_sync.sh"
    VIBE_SKILLS_SYNC_LOADED="$VIBE_LIB/skills_sync.sh"
fi

_skills_help() {
    echo "${BOLD}Vibe Skills Check${NC}"
    echo ""
    echo "Usage: ${CYAN}vibe skills <subcommand>${NC}"
    echo ""
    echo "Subcommands:"
    echo "  ${GREEN}check${NC}     检查 Claude skills / 插件与各 Agent 项目 skills 同步状态"
    echo "  ${GREEN}sync${NC}      已废弃；物理同步请运行 zsh scripts/init.sh"
    echo ""
    echo "💡 物理修复统一交给 ${CYAN}zsh scripts/init.sh${NC}，逻辑审计交给 ${CYAN}/vibe-skills-manager${NC}。"
}

vibe_skills() {
    local subcmd="${1:-check}"
    shift 2>/dev/null || true

    case "$subcmd" in
        check|"")
            echo ""
            echo "🔍 Vibe Skills 状态检查"
            echo ""
            _vibe_skills_check_status
            ;;
        sync)
            log_warn "vibe skills sync 已废弃；物理同步统一由 zsh scripts/init.sh 负责。"
            echo "建议："
            echo "  1. 运行 ${CYAN}zsh scripts/init.sh${NC}"
            echo "  2. 再用 ${CYAN}vibe skills check${NC} 查看状态"
            echo "  3. 如需逻辑治理，使用 ${CYAN}/vibe-skills-manager${NC}"
            ;;
        help|--help|-h) _skills_help ;;
        *)
            log_error "Unknown subcommand: $subcmd"
            _skills_help
            return 1
            ;;
    esac
}
