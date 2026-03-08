#!/usr/bin/env zsh
# lib/flow_help.sh - Help information for Flow module

_flow_usage() {
  echo "${BOLD}Vibe Flow Manager${NC}"
  echo ""
  echo "Usage: ${CYAN}vibe flow <subcommand>${NC} [args]"
  echo ""
  echo "Subcommands:"
  echo "  ${GREEN}new${NC} <name> [--agent <name>] [--branch <ref>]        创建/切换现场（worktree + branch）"
  echo "  ${GREEN}bind${NC} <task-id> [--agent <name>]                    在当前 worktree 内复用环境领取已注册任务"
  echo "  ${GREEN}done${NC}                                                 当前现场收尾（保留 worktree/branch）"
  echo "  ${GREEN}status${NC} [<name>]                                      查看当前分支状态 (默认: 当前分支)"
  echo "  ${GREEN}list${NC}                                                   查看全部分支状态"
  echo "  ${GREEN}pr${NC}                                                   提交代码并打开 Pull Request"
  echo "  ${GREEN}review${NC}                                               查看 PR 或进行本地最终检查"
  echo ""
  echo "Options for 'new <name>':"
  echo "  --agent <name>     指定 AI 身份 (默认: claude)"
  echo "  --branch <ref>     指定基础分支 (默认: main)"
  echo "  # 标准路径：先 vibe task add/update，再 vibe flow new，再 vibe flow bind"
}

_flow_new_usage() { 
    echo "Usage: vibe flow new <name> [--agent=claude] [--branch=main]"
}

_flow_bind_usage() { 
    echo "Usage: vibe flow bind <task-id> [--agent=claude]"
}

_flow_pr_usage() {
  echo "Usage: ${CYAN}vibe flow pr${NC} [options]"
  echo ""
  echo "提交当前工作区的修改并创建/更新 Pull Request。"
  echo "核心职责：判定/校验 PR base -> 执行串行检查 -> 自动处理版本与 CHANGELOG -> 物理 Push -> 云端 PR 关联"
  echo ""
  echo "选项："
  echo "  --base <ref>     显式指定 PR 基线分支；从非 main 近切分支发 PR 时必须传入"
  echo "  --bump <type>    自动版本升级 (patch|minor|major, 默认: patch)"
  echo "  --title <text>   PR 的标题 (默认: 首条 commit 标题)"
  echo "  --body <text>    PR 的正文描述 (默认: 所有 commit 列表)"
  echo "  --msg <text>     写入 CHANGELOG 的版本说明 (默认: 首条 commit...)"
  echo ""
  echo "默认行为："
  echo "  - 仅当当前分支可判定为直接从 main 近切时，才会默认使用 main"
  echo "  - 如果检测到当前分支更接近其他祖先分支，命令会拒绝继续并要求显式 --base"
  echo "  - 这样可以避免把从中间分支派生的变更误向 main 发 PR"
}

_flow_review_usage() {
  echo "Usage: ${CYAN}vibe flow review${NC} [--local] [--json] [<pr-number>|<branch>]"
  echo ""
  echo "审计 PR 的实时真源状态（CI 结果、评审意见、合规性），或执行本地 AI 代码审查。"
  echo "核心职责："
  echo "  1. 状态提取：拉取云端 PR 的评审决策 (Review Decision)"
  echo "  2. 质量审计：实时拉取 CI/Checks 运行状态 (GitHub Actions)"
  echo "  3. 合并判定：自动判断当前真源是否满足 Merge 准入条件"
  echo "  4. 本地审查：使用 --local 调用 codex review 进行深度静态分析与缺陷检测"
  echo ""
  echo "选项："
  echo "  --local     执行本地代码审查（使用 codex）"
  echo "  --json      输出 PR 详细数据的 JSON 格式（用于程序化调用）"
}

_flow_list_usage() {
  echo "Usage: ${CYAN}vibe flow list${NC} [--pr]"
  echo ""
  echo "查看全部分支状态（所有 worktree 的任务进度和物理变动）。"
  echo ""
  echo "默认输出包括："
  echo "  - 每个 worktree 的 task 绑定"
  echo "  - 每个 worktree 的 dirty 状态"
  echo "  - 共享上下文文件数量"
  echo ""
  echo "选项："
  echo "  --pr    查询最近 10 个有 PR 的分支"
}
