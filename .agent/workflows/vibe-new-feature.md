---
name: "Vibe: New Feature"
description: Entry point for new features with orchestrator-driven planning (Discussion Mode)
category: Workflow
tags: [workflow, vibe, planning, orchestrator]
---

# Vibe New Feature(Discussion Mode)

**Input**: 运行 `/vibe-new-feature <goal>` 启动 GitHub-first 的规划引导流程。

## Workflow 定位
- `/vibe-new-feature` 属于 **Discussion Mode (讨论与规划阶段)**。
- 它是调度入口，不是 feature 真源创建器。
- 它的核心职责是围绕 `repo issue`、`GitHub Project item` / `roadmap item`、`task` 与 `flow bind <task-id>` 出具 `plan.md` 图纸。
- **绝对禁止**在该工作流中直接跳步修改非文档业务代码 (`lib/`, `bin/` 等)。

## Shared Task Binding Rules
- 新任务讨论完成后，必须先明确来源层 `repo issue`，再决定是否进入当前规划窗口。
- `roadmap item` 统一解释为 mirrored `GitHub Project item`；其 `type` 可以是 `feature` / `task` / `bug`。
- 本地 `task` 统一解释为 execution record，不是另一套产品规划对象。
- 需要进入执行时，必须通过 shell 命令先写入共享任务真源，再决定绑定到哪个 worktree。
- 所有 registry / worktree / `.vibe/*` 写入都必须通过 shell 命令完成，不得直接手工编辑 JSON 或 Markdown 状态文件。
- `/vibe-new-feature` 当前支持两种 shell 路径：
  - 当前目录开新任务：通过 `vibe task update ... --bind-current` 驱动。
  - 新工作树开新任务：通过 `vibe task add` / `vibe task update` 准备任务元数据；**物理 worktree 的创建/切换由用户在 Shell 中执行** `vibe flow new <slug>` 或 `wt <worktree-name>`，本 workflow 仅负责逻辑分区的绑定。

## Steps

1. **Acknowledge the command**
   立即回复："已进入 Vibe Workflow Engine (Discussion Mode)。我将通过相关 Gate 为您分析与编制执行计划。"

2. **Invoke Scheduler (调度器检查)**
   在调用 orchestrator 之前，先通过调度器检查 GitHub-first 规划状态：
   - 运行 `vibe roadmap status` 获取当前规划窗口
   - 确认是否已有对应 `repo issue`
   - 确认当前规划窗口中是否已有对应 `roadmap item`
   - 若缺少规划项，提示用户先完成 `repo issue -> GitHub Project item -> roadmap item` 的对齐
   - 若已有 `type=feature` 的 roadmap item，则提示后续保持 `1 feature = 1 branch = 1 PR`
   - 若只有 `type=task` 项，则提示其属于 feature 下的执行拆分，不把 `flow new` 当成“定义 feature”

3. **Invoke orchestrator**
   调用 `supervisor/vibe-orchestrator` 技能，将 `<goal>` 作为目标输入。

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
   - 回复用户："✍️ 规划文件 `plan.md` 已就绪。执行引擎已被挂起。请您审查图纸，确认 `repo issue`、`GitHub Project item` / `roadmap item` 与本地 `task` 的关系无误后，再进入执行；**如需创建或切换到新的工作树，请在 Shell 中执行** `vibe flow new` 或 `wt <worktree-name>`，**然后使用** `vibe flow bind <task-id>` **绑定 execution record**。"
