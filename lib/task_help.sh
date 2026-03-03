#!/usr/bin/env zsh
# lib/task_help.sh - Help information for Task module

_vibe_task_usage() {
    echo "${BOLD}Vibe Task Manager${NC}"
    echo ""
    echo "Usage: ${CYAN}vibe task <subcommand>${NC} [args]"
    echo ""
    echo "Subcommands:"
    echo "  ${GREEN}list${NC} [-a|--all] [--json]     列出任务与绑定关系"
    echo "  ${GREEN}add${NC} <title> [--id <id>]      注册新任务记录"
    echo "  ${GREEN}update${NC} <task-id> [options]  更新任务状态、详情或绑定"
    echo "  ${GREEN}remove${NC} <task-id>          从注册表中安全移除任务"
    echo "  ${GREEN}sync${NC}                       同步 OpenSpec 任务至 Registry"
    echo ""
    echo "Options for 'list':"
    echo "  -a, --all        显示包括已完成/已归档在内的所有任务"
    echo "  --json           以 JSON 格式输出合并后的原始数据"
    echo ""
    echo "Options for 'update':"
    echo "  --status <state>  设置状态 (todo, in_progress, completed, archived)"
    echo "  --next-step <txt> 设置当前关注目标或下一步"
    echo "  --branch <ref>    关联 git 分支或基础引用 (如 main)"
    echo "  --bind-current    将任务绑定到当前目录/工作环境"
    echo "  --unassign        解除所有物理 worktree 绑定"
    echo "  --agent <name>    设置操作该任务的 AI 身份"
}
