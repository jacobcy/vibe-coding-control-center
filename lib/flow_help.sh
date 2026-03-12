#!/usr/bin/env zsh
# lib/flow_help.sh - Help information for Flow module

_flow_usage() {
  cat <<EOF
${BOLD}Vibe Flow Manager${NC}
Usage: ${CYAN}vibe flow <subcommand>${NC} [args]
Subcommands:
  ${GREEN}new${NC} <name> [--agent <name>] [--branch <ref>] [--save-unstash]
                                                          在当前目录创建新的逻辑 flow / branch 现场；不创建 planning object，不新建物理 worktree
  ${GREEN}switch${NC} <name>                                       安全进入未关闭且未发过 PR 的现有 flow
  ${GREEN}bind${NC} <task-id> [--agent <name>]                    在当前 worktree 内绑定 existing execution record
  ${GREEN}show${NC} [<flow-name>|<branch>] [--json]                 查看单个 flow 的详情（默认当前 flow）
  ${GREEN}done${NC} [--branch <ref>]                               review-gated merge/close：有 review 证据才允许合并并关闭 flow
  ${GREEN}status${NC} [--json]                                     查看未关闭 flow 大盘
  ${GREEN}list${NC} [--pr]                                          查看所有 flow（含历史）
  ${GREEN}pr${NC} [--base <ref>]                                    提交代码并打开 Pull Request（目标基线分支）
  ${GREEN}review${NC} [--branch <ref>] [--local]                   查看 PR 或产出可回贴的 review evidence
Options for 'new <name>':
  --agent <name>     指定 AI 身份 (默认: claude)
  --branch <ref>     指定当前目录创建新 flow 时的起点分支 (默认: origin/main)
  --save-unstash     将当前未提交改动 stash 后带入新 flow
Options for 'switch <name>':
  dirty worktree     默认自动保存并带入当前未提交改动
Parallel worktree:
  使用 ${CYAN}wtnew${NC} / ${CYAN}vnew${NC} 创建新的物理 worktree；它们不属于 vibe flow 主语义
  物理 worktree 只能由人类明确决定；agent 默认不得自行新建或切换 worktree
  # 用户主链默认按 "repo issue -> flow -> plan/spec -> commit -> PR -> done" 理解 flow 查询输出
  # "vibe flow new/switch" 使用 "--branch" 表示 flow 现场的起点/目标分支；"vibe flow pr" 使用 "--base" 表示 PR 的目标合并分支
  # "vibe flow" 只负责消费已有 task/execution record 并建立运行时现场，不负责创建 roadmap item、repo issue 等规划层对象
EOF
}

_flow_new_usage() { cat <<EOF
Usage: vibe flow new <name> [--agent <name>] [--branch <ref>] [--save-unstash]
  creates a logical runtime container only in the current worktree; create task separately
  does not create a physical worktree
  --branch <ref>  创建 flow 时选择起点分支（默认: origin/main）；不接受 --base
  --save-unstash  将当前未提交改动 stash 后带入新 flow
EOF
}

_flow_switch_usage() { cat <<EOF
Usage: vibe flow switch <name>
  dirty worktree     默认自动保存并带入当前未提交改动
  仅允许进入未关闭且未发过 PR 的现有 flow
EOF
}

_flow_bind_usage() {
  echo "Usage: vibe flow bind <task-id> [--agent <name>]"
  echo "  requires an existing task execution record"
}

_flow_pr_usage() {
  cat <<EOF
Usage: ${CYAN}vibe flow pr${NC} [options]
提交当前工作区的修改并创建/更新 Pull Request。
核心职责：判定/校验 PR base -> 执行串行检查 -> 自动处理版本与 CHANGELOG -> 物理 Push -> 云端 PR 关联
选项：
  --base <ref>     显式指定 PR 目标基线分支；从非 main 近切分支发 PR 时必须传入
  --bump <type>    自动版本升级 (patch|minor|major, 默认: patch)
  --title <text>   PR 的标题 (默认: 首条 commit 标题)
  --body <text>    PR 的正文描述 (默认: 所有 commit 列表)
  --msg <text>     写入 CHANGELOG 的版本说明 (默认: 首条 commit...)
  --web            显式使用 GitHub Web 页面创建 PR；默认直接用 gh CLI 创建
默认行为：
  - 仅当当前分支可判定为直接从 main 近切时，才会默认使用 main
  - 如果检测到当前分支更接近其他祖先分支，命令会拒绝继续并要求显式 --base
  - 提交 PR 前会校验当前分支是否已包含远端最新 base；若落后则拒绝继续
  - 这里的 --base 是 PR 目标分支，不是创建 flow 时的起点分支
  - 默认不打开 Web；只有显式传 '--web' 时才走浏览器创建流程
EOF
}

_flow_show_usage() { cat <<EOF
Usage: ${CYAN}vibe flow show${NC} [<flow-name>|<branch>] [--json]
查看单个 flow 的详情，默认当前 flow。
显示内容：issue refs、spec ref、pr ref、task、branch、state、closed_at、worktree、title、task status、next step。
EOF
}

_flow_status_usage() { cat <<EOF
Usage: ${CYAN}vibe flow status${NC} [--json]
查看未关闭 flow 大盘。
显示内容：
  - open flow 的 flow name / issue / spec / PR / task / next_step
选项：
  --json          以 JSON 格式输出任务数据
EOF
}

_flow_list_usage() { cat <<EOF
Usage: ${CYAN}vibe flow list${NC} [--pr]
查看所有 flow，包括已关闭历史。
默认输出包括：
  - open flow
  - closed flow history
选项：
  --pr    切换到 PR 分支视图（最近 10 条）
EOF
}

_flow_done_usage() {
  cat <<EOF
Usage: ${CYAN}vibe flow done${NC} [--branch <ref>]
关闭当前或指定的 flow，并删除本地/远端分支。
若关闭的是当前分支，当前目录会回到安全的本地 ${CYAN}main${NC} 分支，可直接继续 ${CYAN}vibe flow new${NC}。
核心职责：对未 merged PR 执行 review-gated merge gate；有 review evidence 才允许 merge + closeout。
选项：
  --branch <ref>    指定要完成的分支 (默认: 当前分支)
检查项：
  1. 分支不能是 main 或已关闭 flow
  2. 工作目录必须干净（若关闭当前分支）
  3. 分支必须已有 PR 事实
  4. 若 PR 已 merged，直接走兼容收尾
  5. 若 PR 未 merged，必须先存在 review evidence（Copilot / Codex / local comment 三选一）
  6. 若 PR 未 merged 且已有 review evidence，命令会先尝试 merge，再继续 closeout
EOF
}
