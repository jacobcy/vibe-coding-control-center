#!/usr/bin/env zsh
# lib/flow_help.sh - Help information for Flow module

_flow_usage() {
  echo "${BOLD}Vibe Flow Manager${NC}"
  echo ""
  echo "Usage: ${CYAN}vibe flow <subcommand>${NC} [args]"
  echo ""
  echo "Subcommands:"
  echo "  ${GREEN}start${NC} <feature> [--agent <name>] [--branch <ref>]   注册任务 + 创建沙盒 + 绑定"
  echo "  ${GREEN}start${NC} --task <task-id> [--agent <name>]              在当前 worktree 内领取已注册任务"
  echo "  ${GREEN}done${NC}                                                 结项并彻底清理当前环境"
  echo "  ${GREEN}status${NC} [<feature>]                                   查看沙盒状态与物理变动"
  echo "  ${GREEN}sync${NC}                                                 同步当前变更至所有 worktree"
  echo "  ${GREEN}pr${NC}                                                   提交代码并打开 Pull Request"
  echo "  ${GREEN}review${NC}                                               查看 PR 或进行本地最终检查"
  echo ""
  echo "Options for 'start <feature>':"
  echo "  --agent <name>     指定 AI 身份 (默认: claude)"
  echo "  --branch <ref>     指定基础分支 (默认: main)"
}

_flow_start_usage() { 
    echo "Usage: vibe flow start <feature> | --task <task-id> [--agent=claude] [--branch=main]"
}

_flow_pr_usage() {
  echo "Usage: ${CYAN}vibe flow pr${NC} [options]"
  echo ""
  echo "提交当前工作区的修改并创建/更新 Pull Request。"
  echo "核心职责：执行串行检查 -> 自动处理版本与 CHANGELOG -> 物理 Push -> 云端 PR 关联"
  echo ""
  echo "选项："
  echo "  --bump <type>    自动版本升级 (patch|minor|major, 默认: patch)"
  echo "  --title <text>   PR 的标题 (默认: 首条 commit 标题)"
  echo "  --body <text>    PR 的正文描述 (默认: 所有 commit 列表)"
  echo "  --msg <text>     写入 CHANGELOG 的版本说明 (默认: 首条 commit...)"
}

_flow_review_usage() {
  echo "Usage: ${CYAN}vibe flow review${NC}"
  echo ""
  echo "在 Web 或终端中审阅当前分支绑定的 Pull Request。"
  echo "如果未发现 PR，则退而求其次执行本地健康检查（vibe check）。"
}
