#!/usr/bin/env zsh
# v2/lib/task_help.sh - Help information for Task module

_vibe_task_usage() {
    echo "${BOLD}Vibe Task Manager${NC}"
    echo ""
    echo "Usage: ${CYAN}vibe task <subcommand>${NC} [args]"
    echo ""
    echo "Subcommands:"
    echo "  ${GREEN}list${NC} [-a|--all] [--json]     列出所有任务与绑定关系"
    echo "  ${GREEN}add${NC} --title <text>           创建新任务"
    echo "  ${GREEN}update${NC} <id> [options]         更新任务状态、绑定或下一步"
    echo "  ${GREEN}remove${NC} <id>                 删除任务"
    echo "  ${GREEN}sync${NC}                       同步 OpenSpec 变更至 Registry"
    echo ""
    echo "Options for 'update':"
    echo "  --status <state>            设置状态 (todo, in-progress, completed, archived)"
    echo "  --next-step <text>          设置当前关注的目标/下一步"
    echo "  --bind-current              将任务绑定到当前目录"
    echo "  --unassign                  解除所有 worktree 绑定"
    echo "  --agent <name>              设置操作该任务的 AI 身份"
}
