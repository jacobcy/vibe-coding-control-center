#!/usr/bin/env zsh
# lib/skills.sh - Skills CLI dispatcher

if [[ "${VIBE_SKILLS_SYNC_LOADED:-}" != "$VIBE_LIB/skills_sync.sh" ]]; then
    source "$VIBE_LIB/skills_sync.sh"
    VIBE_SKILLS_SYNC_LOADED="$VIBE_LIB/skills_sync.sh"
fi

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
}

vibe_skills() {
    local subcmd="${1:-help}"
    shift 2>/dev/null || true
    vibe_require jq || return 1
    [[ -f "$(_vibe_skills_registry_file)" ]] || vibe_die "Missing registry: $(_vibe_skills_registry_file)"

    echo ""
    echo "🔄 Vibe Skills 同步工具"
    echo ""

    case "$subcmd" in
        sync|"")
            vibe_require npx || return 1
            _vibe_skills_sync_claude_plugin
            _vibe_skills_sync_global_superpowers
            _vibe_skills_sync_local_skills
            _vibe_skills_run_audit
            log_success "同步完成！"
            ;;
        check) _vibe_skills_check_status ;;
        help|--help|-h) _skills_help ;;
        *)
            log_error "Unknown subcommand: $subcmd"
            _skills_help
            return 1
            ;;
    esac
}
