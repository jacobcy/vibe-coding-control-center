# Task Status

## Current

- current task: `2026-03-02-cross-worktree-task-registry`
- current worktree: `wt-claude-refactor`
- shared source of truth: `$(git rev-parse --git-common-dir)/vibe/registry.json`
- worktree binding: `$(git rev-parse --git-common-dir)/vibe/worktrees.json`
- local cache: `.vibe/current-task.json`, `.vibe/focus.md`, `.vibe/session.json`
- compat note: 在所有 skills 迁移完成前，`.agent/context/task.md` 仅保留 current task 摘要和 worktree 绑定说明，不再作为 task 真源。
- gitignore note: `.vibe/` 为本地缓存目录，必须保持忽略状态。

## Task Model

- 单个 worktree 同时只绑定一个 current task。
- task 可以没有 subtask，也可以包含多个 optional subtasks。
- 当前 worktree 只继续自己的 current task，不负责跨 worktree 选择。
- 新任务必须先写入共享 registry，再生成本地 `.vibe/current-task.json` 指针。

## Recent

- **git-workflow-standard** (framework: none)
  - status: completed
  - completed: 2026-02-28
  - 产出：
    - `docs/standards/git-workflow-standard.md`
    - 更新 `docs/prds/vibe-workflow-paradigm.md`
    - 更新 `CLAUDE.md`

- **docs-organization-standard** (framework: vibe-workflow)
  - status: completed
  - completed: 2026-02-28
  - 产出：
    - 重组 docs 目录结构，符合 doc-organization.md 标准
    - 创建 5 个任务目录，每个包含 README.md
    - 移动 20+ 文档到正确位置
    - 统一文件命名为 kebab-case
    - 清理空目录（specs/plans/reviews/tech/governance）
  - 任务分类：
    - `docs/tasks/2026-02-26-agent-dev-refactor/` - Agent 工具链重构（已归档）
    - `docs/tasks/2026-02-25-vibe-v2-final/` - Vibe V2 最终方案（已归档）
    - `docs/tasks/2026-02-21-save-command/` - Save Command 设计（已归档）
    - `docs/tasks/2026-02-21-vibe-architecture/` - Vibe 架构设计（已归档）
    - `docs/tasks/2026-02-26-vibe-engine/` - Vibe Engine 实现（已归档）

## Recent

- **vibe-workflow-paradigm PRD 编写** (framework: superpower)
  - status: completed
  - completed: 2026-02-27
  - 产出：
    - `docs/prds/vibe-workflow-paradigm.md` - 总 PRD
    - `docs/prds/plan-gate-enhancement.md` - Plan Gate 多源读取
    - `docs/prds/spec-critic.md` - AI 刺客找茬
    - `docs/prds/collusion-detector.md` - 串通检测
    - `docs/prds/context-scoping.md` - 上下文圈定

- unified-dispatcher (framework: none)
  - status: completed
  - 产出：`docs/prds/unified-dispatcher.md`

- 文档精简与去重（token 优化）
  - status: completed
  - 目标文件：`SOUL.md` `CLAUDE.md` `README.md` `.agent/context/*` `.agent/rules/*`

- 已恢复 PR #12 内容（通过恢复 PR #13 合并到 main）
- 已启用 main 分支保护（禁止 force push，强制 PR + 检查）

## Backlog（待补齐 PRD）

按优先级排序：

| 优先级 | PRD | 对应范式层 | 说明 |
| ------ | --- | ---------- | ---- |
| P1 | test-layer | 第 4 层 Test | TDD 顺序（先 Red 再 Green）、3 次熔断机制 |
| P2 | code-layer | 第 5 层 Code | AST 级约束、复杂度熔断（需确认 vibe-boundary-check 覆盖情况） |
| P3 | rules-enforcer | 第 6 层 AI Audit | vibe-rules-enforcer 审计报告格式、检查项定义 |
