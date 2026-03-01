---
task_id: "2026-03-02-cross-worktree-task-registry"
document_type: task-readme
title: "Cross-Worktree Task Registry"
current_layer: "plan"
status: "in-progress"
author: "Codex GPT-5"
created: "2026-03-02"
last_updated: "2026-03-02"
related_docs:
  - docs/standards/git-workflow-standard.md
  - docs/tasks/2026-03-01-session-lifecycle/plan-v1-checkpoint.md
  - .agent/context/task.md
  - .agent/context/memory.md
gates:
  scope:
    status: "passed"
    timestamp: "2026-03-02T00:00:00+08:00"
    reason: "问题已收敛为跨 worktree 的任务绑定、选择与监控，不再是单 worktree session 恢复。"
  spec:
    status: "passed"
    timestamp: "2026-03-02T00:00:00+08:00"
    reason: "已明确关键约束：任务可选拆分 subtask；每个 worktree 同时只绑定一个当前 task；本地聚焦内容放 worktree `.vibe/` 并加入 `.gitignore`。"
  plan:
    status: "passed"
    timestamp: "2026-03-02T00:00:00+08:00"
    reason: "已生成 plan-v1-initial.md，用于定义共享任务注册表和 worktree 绑定模型。"
  test:
    status: "pending"
    timestamp: ""
    reason: ""
  code:
    status: "pending"
    timestamp: ""
    reason: ""
  audit:
    status: "pending"
    timestamp: ""
    reason: ""
---

# Task: Cross-Worktree Task Registry

## 概述

当前系统能在单个 worktree 内恢复最近一次 session，但缺少跨 worktree 的统一任务视图，导致多任务并行时无法快速判断应进入哪个 worktree，也无法监控多个 worktree 上的 task 执行状态。

本任务将先设计一个跨 worktree 的共享任务注册表，定义任务、子任务与 worktree 的绑定关系，再决定如何让现有 session checkpoint 方案接入该真源。

## 当前状态

- **层级**: Plan（执行计划层）
- **状态**: In Progress
- **最后更新**: 2026-03-02

## Gate 进展

| Gate | 状态 | 时间 | 备注 |
|------|------|------|------|
| Scope Gate | Passed | 2026-03-02 | 已确认问题属于跨 worktree 任务编排，不并入现有 checkpoint 小任务 |
| Spec Gate | Passed | 2026-03-02 | 已确认 task/subtask 模型、worktree 绑定规则与本地 `.vibe/` 缓存边界 |
| Plan Gate | Passed | 2026-03-02 | 已生成初版实施计划 |
| Test Gate | Pending | - | 待执行阶段定义验证命令 |
| Code Gate | Pending | - | 待实现 |
| Audit Gate | Pending | - | 待审计 |

## 文档导航

### Plan（执行计划层）
- [plan-v1-initial.md](plan-v1-initial.md)

### Related Design
- [session-checkpoint plan](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/tasks/2026-03-01-session-lifecycle/plan-v1-checkpoint.md)
- [git-workflow standard](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/git-workflow-standard.md)

## 关键约束

- 任务模型统一为 `task + optional subtasks`，不再区分 `major/minor`。
- 每个 worktree 在任一时刻只绑定一个当前 task。
- `vibe-continue` 只负责继续当前 worktree 绑定的 task，不负责跨 worktree 路由。
- 任务与 memory 的真源需要迁移到共享位置，不能继续依赖每个 worktree 的独立副本。
- worktree 本地聚焦内容放在 `.vibe/`，并加入 `.gitignore`，避免合并负担。
- session checkpoint 后续必须依附共享任务真源，而不是继续扩展成独立状态系统。

## 非目标

- 本任务不直接实现 session checkpoint。
- 本任务不直接实现 Shell 层 worktree 创建/销毁逻辑。
- 本任务不引入跨 worktree 的实时协同或锁服务。
- 本任务不新增 `vibe-switch` 这种跨 worktree 对话切换入口。

## 当前设计结论

- 当前仓库的共享真源固定放在 `$(git rev-parse --git-common-dir)/vibe/`。
- `~/.vibe/` 仅保存全局配置和可选的跨仓库索引，不保存当前仓库的任务真源。
- 共享真源保存所有 task、subtasks、状态、next step、共享 memory 与 worktree 绑定关系。
- 当前 worktree 的 `.vibe/` 只保存可丢弃的聚焦内容，例如当前任务指针、focus 摘要、session 缓存。
- `vibe-save` 默认写回共享真源，并可顺手刷新当前 worktree 的 `.vibe/`。
- 后续应新增 `vibe-task` 用于跨 worktree 总览，而不是扩展 `vibe-continue` 去做调度。

## 状态枚举（V1）

- `task.status` / `subtask.status`
  - `todo`
  - `in_progress`
  - `blocked`
  - `done`
  - `archived`
- `worktree.status`
  - `active`
  - `idle`
  - `missing`

## 参考

- [Git Workflow & Worktree Lifecycle Standard](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/git-workflow-standard.md)
- [Session Checkpoint 实施计划](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/tasks/2026-03-01-session-lifecycle/plan-v1-checkpoint.md)
