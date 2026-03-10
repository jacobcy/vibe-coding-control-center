---
name: "Vibe: New"
description: Entry point for new features with orchestrator-driven planning (Discussion Mode)
category: Workflow
tags: [workflow, vibe, planning, orchestrator]
---

# Vibe New (Discussion Mode)

**Input**: 运行 `/vibe-new <goal-or-slug> [--save-unstash]` 启动新功能引导流程。

## Workflow 定位
- `/vibe-new` 属于 **Discussion Mode (讨论与规划阶段)**。
- 它的核心职责是出具 `plan.md` 图纸。**绝对禁止**在该工作流中直接跳步修改非文档业务代码 (`lib/`, `bin/` 等)。
- `/vibe-new` 是调度与规划入口，不负责直接定义 `repo issue`、roadmap item、task 或 flow 真源。

## Shared Task / Flow Setup Rules
- 新任务讨论完成后，必须先通过 shell 命令写入共享真源，再决定由哪个 worktree 承载对应的 flow。
- 所有 registry / worktree runtime 写入都必须通过 shell 命令完成，不得直接手工编辑 JSON 或 Markdown 状态文件。
- `/vibe-new` 当前支持两种 shell 路径：
   - 当前目录承载既有 execution record：通过 `vibe task update ... --bind-current` 让当前目录承载的 flow 对应到目标 task。
  - 新目录准备执行现场：先通过 `vibe task add` / `vibe task update` 准备 task execution record，再调用 `vibe flow new <slug> --agent <agent>` 创建/切换 worktree。
   - 如需让已有 worktree 承载目标 task 对应的 flow，使用 `vibe flow bind <task-id> --agent <agent>`。
  - 若不确定 shell 参数，先运行 `vibe flow -h` 或 `vibe task -h`，不要自造命令形式。

## Dirty Worktree Rotation Rule
- 当用户在当前 worktree 存在未提交改动（尤其是 unstaged/untracked）且需要开新分支时，按参数显式控制：
  - 默认（不传 `--save-unstash`）：`zsh scripts/rotate.sh <new-branch-name>`
    - 行为：先 `stash -u` 保存当前改动，但不自动回放到新分支（新分支保持干净）
  - 传 `--save-unstash`：`zsh scripts/rotate.sh <new-branch-name> --save-unstash`
    - 行为：先 `stash -u` 保存，再在新分支自动 `stash pop` 回放改动
- 仅当没有未提交改动，或用户明确不走 rotate 流程时，才可以直接走 `vibe flow new <slug> --agent <agent>` / `vibe flow bind <task-id> --agent <agent>`。

## Steps

1. **Acknowledge the command**
   立即回复："已进入 Vibe Workflow Engine (Discussion Mode)。我将通过相关 Gate 为您分析与编制执行计划。"

2. **Invoke Scheduler (调度器检查)**
   在调用 orchestrator 之前，先通过调度器检查当前规划窗口状态：
   - 运行 `vibe roadmap status` 获取当前 roadmap / 规划窗口
   - 如果没有设置版本目标或等价规划窗口，则提示用户：
     "当前没有设置规划窗口。请先使用 `vibe roadmap assign <目标>` 确定当前版本目标或阶段目标，再来领任务。"
   - 如果有规划窗口，检查当前窗口是否已有 `P0` 或 `current` 的 roadmap item
   - 如果没有可执行的 roadmap item，提示用户先完成 `repo issue -> roadmap item` 的纳入，再进入 task / flow 讨论

3. **Invoke orchestrator**
   调用 `supervisor/vibe-orchestrator` 技能，将 `<goal-or-slug>` 作为目标输入。

4. **Run Planning Gates**
   严格按以下顺序推进：
   - Gate 0: Intent Gate (智能调度与任务初始化)
   - Gate 1: Scope Gate (边界检查)
   - Gate 2: Spec Gate (契约校验)
   - Gate 3: Plan Gate (出具 `plan.md` 执行图纸)

5. **Exception Escalation Hook (举报通道)**
   在任何一个 Gate 中，如果发现严重异常（如系统配置确实、严重越界，或文档严重缺损）：
   - 立刻终止后续探索，不允许敷衍或胡编乱造。
   - 抛出红色 🚨 警告，向 Orchestrator 提报错误并等待人类指挥。

6. **Checkpoint Output & HARD STOP**
   - 每通过一个 Gate，输出判定结果与下一步。
   - 一旦生成并审查了 `plan.md`，即表示 Gate 3 完成。必须触发 **HARD STOP（硬停止）**。
   - 回复用户："✍️ 规划文件 `plan.md` 已就绪。执行引擎已被挂起。请您审查图纸，若无异议，请回复 `/vibe-start` 唤醒 Execution 机器人开始编码；如需在 shell 中新建 worktree 或让现有目录承载目标 flow，请使用 `vibe flow new <slug> --agent <agent>` 或 `vibe flow bind <task-id> --agent <agent>`。注意：`vibe flow new (shell)` 只创建执行现场，不定义 feature 或 roadmap item。若当前有未提交改动且要开新分支，默认执行 `zsh scripts/rotate.sh <new-branch-name>`（不带改动）；若需带入改动，请执行 `zsh scripts/rotate.sh <new-branch-name> --save-unstash`。"
