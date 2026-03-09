#!/usr/bin/env zsh
# lib/flow_help.sh - Help information for Flow module

_flow_usage() {
  echo "${BOLD}Vibe Flow Manager${NC}"
  echo ""
  echo "Usage: ${CYAN}vibe flow <subcommand>${NC} [args]"
  echo ""
  echo "Subcommands:"
  echo "  ${GREEN}new${NC} <name> [--agent <name>] [--branch <ref>]        创建新的物理现场（当前为 worktree + branch 过渡语义）"
  echo "  ${GREEN}switch${NC} <name> [--branch <ref>] [--save-stash]       在当前目录进入/切换逻辑 flow"
  echo "  ${GREEN}bind${NC} <task-id> [--agent <name>]                    在当前 worktree 内复用环境领取已注册任务"
  echo "  ${GREEN}done${NC} [--branch <ref>]                               当前/指定现场收尾（保留 worktree/branch）"
  echo "  ${GREEN}status${NC} [--branch <ref>]                             查看当前/指定分支状态"
  echo "  ${GREEN}list${NC}                                                   查看当前未关闭 flow 列表"
  echo "  ${GREEN}pr${NC} [--base <ref>]                                    提交代码并打开 Pull Request（目标基线分支）"
  echo "  ${GREEN}review${NC} [--branch <ref>] [--local]                   查看 PR 或进行本地最终检查"
  echo ""
  echo "Options for 'new <name>':"
  echo "  --agent <name>     指定 AI 身份 (默认: claude)"
  echo "  --branch <ref>     指定创建现场时的起点分支 (默认: main)"
  echo "Options for 'switch <name>':"
  echo "  --branch <ref>     指定新逻辑 flow 的起点分支 (默认: main)"
  echo "  --save-stash       将当前未提交改动 stash 后带入新 flow"
  echo "  # 标准路径：当前目录串行切 flow 用 vibe flow switch；并行新物理现场用 vibe flow new / wtnew"
  echo "  # 概念边界：flow new/new worktree 与 flow switch/reuse current worktree 不是一回事"
  echo "  # 参数边界：flow new/switch 用 --branch；flow pr 用 --base；两者不是同义参数"
}

_flow_new_usage() { 
    echo "Usage: vibe flow new <name> [--agent <name>] [--branch <ref>]"
    echo "  --branch <ref>  创建 flow 时选择起点分支；不接受 --base"
}

_flow_switch_usage() {
    echo "Usage: vibe flow switch <name> [--branch <ref>] [--save-stash]"
    echo "  --branch <ref>     在当前目录进入新的逻辑 flow 时使用的起点分支"
    echo "  --save-stash       将未提交改动 stash 后带入新 flow"
}

_flow_bind_usage() { 
    echo "Usage: vibe flow bind <task-id> [--agent <name>]"
}

_flow_pr_usage() {
  echo "Usage: ${CYAN}vibe flow pr${NC} [options]"
  echo ""
  echo "提交当前工作区的修改并创建/更新 Pull Request。"
  echo "核心职责：判定/校验 PR base -> 执行串行检查 -> 自动处理版本与 CHANGELOG -> 物理 Push -> 云端 PR 关联"
  echo ""
  echo "选项："
  echo "  --base <ref>     显式指定 PR 目标基线分支；从非 main 近切分支发 PR 时必须传入"
  echo "  --bump <type>    自动版本升级 (patch|minor|major, 默认: patch)"
  echo "  --title <text>   PR 的标题 (默认: 首条 commit 标题)"
  echo "  --body <text>    PR 的正文描述 (默认: 所有 commit 列表)"
  echo "  --msg <text>     写入 CHANGELOG 的版本说明 (默认: 首条 commit...)"
  echo ""
  echo "默认行为："
  echo "  - 仅当当前分支可判定为直接从 main 近切时，才会默认使用 main"
  echo "  - 如果检测到当前分支更接近其他祖先分支，命令会拒绝继续并要求显式 --base"
  echo "  - 这样可以避免把从中间分支派生的变更误向 main 发 PR"
  echo "  - 概念边界：这里的 --base 是 PR 要合入的目标分支，不是创建 flow 时的起点分支"
}

_flow_status_usage() {
  echo "Usage: ${CYAN}vibe flow status${NC} [--branch <ref>] [--json]"
  echo ""
  echo "查看当前或指定分支的任务状态、进度和工作区信息。"
  echo ""
  echo "显示内容："
  echo "  - 绑定到分支的任务 ID、标题、状态"
  echo "  - 任务当前阶段（Draft/Planning/Implementation/Review）"
  echo "  - 下一步操作建议"
  echo "  - 工作区物理状态（未提交文件数量）"
  echo "  - 代码库度量信息"
  echo ""
  echo "选项："
  echo "  --branch <ref>  指定要查看的分支 (默认: 当前分支)"
  echo "  --json          以 JSON 格式输出任务数据"
}

_flow_list_usage() {
  echo "Usage: ${CYAN}vibe flow list${NC} [--pr]"
  echo ""
  echo "查看未关闭 flow 列表（逻辑层：registry 中 status 属于 todo/in_progress/blocked）。"
  echo ""
  echo "默认输出包括："
  echo "  - flow task id / title / status"
  echo "  - flow next_step（若存在）"
  echo "  - 不展示 worktree 物理层状态"
  echo ""
  echo "选项："
  echo "  --pr    切换到 PR 分支视图（最近 10 条）"
}

_flow_done_usage() {
  echo "Usage: ${CYAN}vibe flow done${NC} [--branch <ref>]"
  echo ""
  echo "完成当前或指定的 flow 现场，检查分支是否已合并到 origin/main。"
  echo "核心职责：验证工作已完成并合并，保留 worktree/branch 供后续清理。"
  echo ""
  echo "选项："
  echo "  --branch <ref>    指定要完成的分支 (默认: 当前分支)"
  echo ""
  echo "检查项："
  echo "  1. 分支不能是 main 或主 worktree"
  echo "  2. 工作目录必须干净（无未提交修改）"
  echo "  3. 分支的所有提交必须已合并到 origin/main"
  echo ""
  echo "示例："
  echo "  ${CYAN}vibe flow done${NC}                    # 完成当前分支"
  echo "  ${CYAN}vibe flow done --branch task/fix-bug${NC}  # 完成指定分支"
}
