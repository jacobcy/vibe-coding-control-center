---
description: 新功能统一入口，调用 Vibe Orchestrator 执行 Vibe Guard 流程。
---

# Vibe New

**Input**: 运行 `/vibe-new <feature>` 启动新功能引导流程。

## Shared Task Binding Rules

- `/vibe-new` 只负责智能入口编排，不得直接修改共享 registry、worktree 绑定或本地 `.vibe/*` 文件。
- 新任务讨论完成后，必须通过 shell 命令先写入共享任务真源 `$(git rev-parse --git-common-dir)/vibe/`，再决定绑定到哪个 worktree。
- 共享真源至少维护：
  - `registry.json`：task 摘要索引
  - `worktrees.json`：worktree 与 current task 绑定
  - `tasks/<task-id>/task.json`：单 task 真源，可包含 optional subtasks
- 目标 worktree 只保存本地 `.vibe/` 缓存：
  - `.vibe/current-task.json`：当前 current task 指针
  - `.vibe/focus.md`：聚焦摘要
  - `.vibe/session.json`：短期会话缓存
- `.vibe/` 不是 task 真源，必须加入 gitignore，内容可重建。
- `/vibe-new` 当前支持两种 shell 路径：
  - 当前目录开新任务：通过 `vibe task update ... --bind-current` 与 `vibe flow start --task <task-id>` 驱动。
  - 新目录开新任务：通过 `vibe task` 配置任务，再调用 `vibe flow start <feature>` 创建/切换 worktree。

**Steps**

1. **Acknowledge the command**
   立即回复："已进入 Vibe Workflow Engine。我将通过 Vibe Guard 流程（Scope/Plan/Execution/Review 等）引导本次开发。"

2. **Invoke orchestrator**
   必须调用 `vibe-orchestrator` 技能，并将 `<feature>` 作为目标输入。

3. **Run Gate Flow**
   严格按 Vibe Guard 以下顺序推进：
   - Scope Gate（边界检查）
   - Spec Gate（契约校验）
   - Plan Gate（计划校验/补齐）
   - Test Gate（测试覆盖）
   - Execution Gate（按计划执行并验证）
   - Audit/Review Gate（合规与结果复核）

4. **Checkpoint Output**
   每通过一个 Gate，输出：
   - 当前 Gate
   - 判定结果（通过/阻断）
   - 下一步动作

5. **Task / Worktree Binding**
   在进入 Execution 前，必须明确：
   - 当前 worktree 的 current task
   - task 是否包含 subtasks
   - 当前是“当前目录开新任务”还是“新目录开新任务”
   - 所有 registry / worktree / `.vibe/*` 写入都必须通过 shell 命令完成，不得直接手工编辑 JSON 或 Markdown 状态文件
   - 当前目录模式：优先调用 `vibe task update <task-id> --bind-current ...`，再调用 `vibe flow start --task <task-id>`
   - 新目录模式：先用 `vibe task add` / `vibe task update` 准备任务元数据，再调用 `vibe flow start <feature>`

6. **Blocking Policy**
   任一 Gate 阻断时，停止继续执行后续 Gate，并给出恢复路径。
