---
task_id: "2026-03-02-rotate-alignment"
document_type: task-plan
title: "Rotate Workflow Refinement Plan"
author: "Antigravity Agent"
created: "2026-03-02"
last_updated: "2026-03-02"
status: planning
---

# 1. 现状痛点
目前的开发链路是 `start -> ... -> pr`。由于 GitHub 侧采用 Squash 合并策略，PR 合成一个点后，本地发版分支并不知道远端的最新状态，其历史里仍然散落着原本的开发链条。
此时如果不想关闭沙盒（`vibe flow done`），直接拿这个分支继续写，下一个发起的 PR 就会出现大量前一单的祖传 Commit 幽灵。

现存的 `scripts/rotate.sh <new_branch>` 能够强制放弃旧名字旧壳、通过 fetch `origin/main` 产生纯净新分支。
但
1. 它是一个隐形的脚本，普通开发者并不知道可以通过执行这个脚本达到 "原地续命" 的重开效果。
2. 它脱离于当前极智的 `/vibe_xxx` 大盘，旋转完后不会告知 Task Registry 也不会刷新 `.vibe/current-task.json` 挂件。
3. 它没有“原地重置”能力（像 `git reset --hard` 同名续命）。

# 2. 规划：双面升级（Command + Slash）

## 环节一：Shell API 正规军化 (lib/flow.sh)
将现有的 `scripts/rotate.sh` 收割进入 `vibe flow`：
引入：**`vibe flow rotate [new-branch-name | --force-reset]`**
- 动作 1：如果不带名字只带 `--force-reset`，执行本地危险操作警告。警告确立后，清理未提交工作、`fetch origin main`、并极其暴力地原地 `git reset --hard origin/main`。
- 动作 2：带上 `<new-branch-name>` 时，平移使用原来的暂存+切新枝逻辑。
- 动作 3：一旦发生分支变迁，主动清理重置原本残留在该 worktree 上的关联 `.vibe/` 挂件，阻断任务串改。

## 环节二：Slash AI 包装 (skills/vibe-rotate)
设立 `/vibe-rotate` 技能：
- “全能后悔药 / 快速开局机”，在对话窗中执行。
- 让向 AI 求助的开发者能在 PR 刚融完或写疵代码时直接输入 `/vibe-rotate`。
- Agent 获取此时代码的脏状态、确认上次 PR 信息，并通过控制台帮他执行相应的安全重置语句（调用 `vibe flow rotate` 家族命令）。 

# 3. 落地实施路线 (To Be Executed)
- **Phase A**: 提权重构 `rotate.sh` 至 `lib/flow.sh` 的指令树。
- **Phase B**: 将 `/vibe-rotate` 载入 `tasks` 及 `workflows` 大盘，加入系统默认可用技能列表。
- **Phase C**: 整合前述计划的 Task Registry 更新机制，将其在完成切枝后同时完结前置分支的任务状态。
