---
name: "Vibe: New"
description: Entry point for new features with orchestrator-driven planning (Discussion Mode)
category: Workflow
tags: [workflow, vibe, planning, orchestrator]
---

# Vibe New (Discussion Mode)

**Input**: 运行 `/vibe-new <feature> [--save-unstash]` 启动新功能引导流程。

## Workflow 定位
- `/vibe-new` 属于 **Discussion Mode (讨论与规划阶段)**。
- 它的核心职责是出具 `plan.md` 图纸。**绝对禁止**在该工作流中直接跳步修改非文档业务代码 (`lib/`, `bin/` 等)。

## Shared Task Binding Rules
- 新任务讨论完成后，必须通过 shell 命令先写入共享任务真源，再决定绑定到哪个 worktree。
- 所有 registry / worktree / `.vibe/*` 写入都必须通过 shell 命令完成，不得直接手工编辑 JSON 或 Markdown 状态文件。
- `/vibe-new` 当前支持两种 shell 路径：
  - 当前目录开新任务：通过 `vibe task update ... --bind-current` 驱动。
  - 当前目录切到下一个逻辑 flow：通过 `vibe task add` / `vibe task update` 准备任务元数据，再调用 `vibe flow new <feature> --agent <agent> [--branch <ref>] [--save-unstash]` 在当前目录创建新的 flow / branch。
  - 并行新目录隔离：使用 `wtnew` / `vnew` 创建新的物理 worktree；它们不属于 `vibe flow` 主语义。
  - 如需在已有 worktree 绑定任务，使用 `vibe flow bind <task-id> --agent <agent>`。
  - 若不确定 shell 参数，先运行 `vibe flow -h` 或 `vibe task -h`，不要自造命令形式。

## Dirty Worktree Rotation Rule
- 当用户在当前 worktree 存在未提交改动（尤其是 unstaged/untracked）且需要开新分支时，按参数显式控制：
  - 默认（不传 `--save-unstash`）：`vibe flow new <feature> --agent <agent> [--branch <ref>]`
    - 行为：工作区必须干净，否则 shell 直接阻断
  - 传 `--save-unstash`：`vibe flow new <feature> --agent <agent> [--branch <ref>] --save-unstash`
    - 行为：先 `stash -u` 保存，再在新 flow 自动 `stash pop` 回放改动
- 不再把 `scripts/rotate.sh` 作为推荐主路径；它只保留兼容包装角色。
- `.agent/context/task.md` 只作为本地 handoff 记录，不得写成共享任务真源。

## Steps

1. **Acknowledge the command**
   立即回复："已进入 Vibe Workflow Engine (Discussion Mode)。我将通过相关 Gate 为您分析与编制执行计划。"

2. **Invoke Scheduler (调度器检查)**
   在调用 orchestrator 之前，先通过调度器检查版本目标状态：
   - 运行 `vibe roadmap status` 获取当前版本目标
   - 如果没有设置版本目标（version_goal = none），则提示用户：
     "当前没有设置版本目标。请先使用 `vibe roadmap assign <目标>` 确定本版本要完成的目标，然后再来领任务。"
   - 如果有版本目标，检查当前版本是否有 P0 或 current 状态的任务
   - 如果没有可执行的任务，提示用户使用 `vibe roadmap classify <issue-id> --status current` 将 Issue 纳入当前版本

3. **Invoke orchestrator**
   调用 `supervisor/vibe-orchestrator` 技能，将 `<feature>` 作为目标输入。

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
  - 回复用户："✍️ 规划文件 `plan.md` 已就绪。执行引擎已被挂起。请您审查图纸，若无异议，请回复 `/vibe-start` 唤醒 Execution 机器人开始编码；如需在当前目录创建或绑定 flow，请使用 `vibe flow new <feature> --agent <agent> [--branch <ref>] [--save-unstash]` 或 `vibe flow bind <task-id> --agent <agent>`。若需要新的物理 worktree，请使用 `wtnew` / `vnew`。"
