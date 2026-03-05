---
description: 新功能统一入口，调用 Vibe Orchestrator 负责意图分析与方案规划 (Discussion Mode)。
---

# Vibe New (Discussion Mode)

**Input**: 运行 `/vibe-new <feature>` 启动新功能引导流程。

## Workflow 定位
- `/vibe-new` 属于 **Discussion Mode (讨论与规划阶段)**。
- 它的核心职责是出具 `plan.md` 图纸。**绝对禁止**在该工作流中直接跳步修改非文档业务代码 (`lib/`, `bin/` 等)。

## Shared Task Binding Rules
- 新任务讨论完成后，必须通过 shell 命令先写入共享任务真源，再决定绑定到哪个 worktree。
- 所有 registry / worktree / `.vibe/*` 写入都必须通过 shell 命令完成，不得直接手工编辑 JSON 或 Markdown 状态文件。
- `/vibe-new` 当前支持两种 shell 路径：
  - 当前目录开新任务：通过 `vibe task update ... --bind-current` 驱动。
  - 新目录开新任务：通过 `vibe task add` / `vibe task update` 准备任务元数据，再调用 `vibe flow create <feature>` 创建/切换 worktree。

## Steps

1. **Acknowledge the command**
   立即回复："已进入 Vibe Workflow Engine (Discussion Mode)。我将通过相关 Gate 为您分析与编制执行计划。"

2. **Invoke orchestrator**
   调用 `supervisor/vibe-orchestrator` 技能，将 `<feature>` 作为目标输入。

3. **Run Planning Gates**
   严格按以下顺序推进：
   - Gate 0: Intent Gate (智能调度与任务初始化)
   - Gate 1: Scope Gate (边界检查)
   - Gate 2: Spec Gate (契约校验)
   - Gate 3: Plan Gate (出具 `plan.md` 执行图纸)

4. **Exception Escalation Hook (举报通道)**
   在任何一个 Gate 中，如果发现严重异常（如系统配置确实、严重越界、或文档严重缺损）：
   - 立刻终止后续探索，不允许敷衍或胡编乱造。
   - 抛出红色 🚨 警告，向 Orchestrator 提报错误并等待人类指挥。

5. **Checkpoint Output & HARD STOP**
   - 每通过一个 Gate，输出判定结果与下一步。
   - 一旦生成并审查了 `plan.md`，即表示 Gate 3 完成。必须触发 **HARD STOP（硬停止）**。
   - 回复用户：“✍️ 规划文件 `plan.md` 已就绪。执行引擎已被挂起。请您审查图纸，若无异议，请回复 `/vibe-start` 唤醒 Execution 机器人开始编码；如需在 shell 中创建或绑定 worktree，请使用 `vibe flow new` 或 `vibe flow bind`。”
