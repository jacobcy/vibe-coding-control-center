---
title: roadmap shell and skill current-state audit
date: 2026-03-08
status: open
scope: roadmap-shell-skill
---

# Current State Audit

本文档记录当前 `roadmap` 相关 shell 与 skill 的实际状态，用于后续收敛实现。

## Confirmed Clarifications

- `roadmap.current` 是全局规划窗口状态，不是分支当前态
- branch / worktree 当前在做什么，应由 `flow` 与 task runtime 绑定表达
- `issue` 是愿望或外部输入，不等于 `task`
- `task` 是明确、可执行、可落地的工作单元
- `flow` 是 task 的运行时容器，通常绑定一个 worktree / branch，并通常对应一个 PR

## Relationship Model

- `issue <-> task`：多对多
- `roadmap item <-> task`：多对多
- `flow -> task`：一对多

这意味着：

- 一个 issue 不能假定一次完成
- 一个 issue 可以拆成多个本地 task
- 一个 flow 可以承载若干相关 task
- `roadmap current` 不能承担“各个分支分别当前做什么”的语义

## Shell Audit

### Overreach

- `vibe roadmap classify` 在 item 不存在时会自动新增 roadmap item
- 这属于隐藏 workflow，不是纯分类动作

### Capability Gaps

- `vibe roadmap` 还没有显式 link / unlink task 的原子能力
- `vibe task` 还没有完整的 `--issue-ref` / `--roadmap-item` 原子关系写入能力
- `vibe flow new` 仍需进一步收紧为纯现场创建

### Standard Drift

- `roadmap` 写操作尚未全面落实 `-y/--yes`
- `roadmap skill` 的“从当前 backlog 分配最高优先级任务”描述超前于当前 shell 能力

## Skill Audit

`skills/vibe-roadmap/SKILL.md` 的主边界方向是正确的：

- 明确 CLI 负责读写
- 明确 skill 负责调度决策
- 明确不得直接改底层数据

但还需要继续收紧两点：

- 不应暗示 `roadmap current` 等于“当前 branch 应做的事”
- 不应暗示仅调用现有 shell 命令就能直接完成 roadmap -> task -> flow 的完整业务逻辑

## Immediate Follow-Up

1. 修正 `roadmap classify`，禁止隐式新增 roadmap item
2. 为 `task add` / `task update` 补齐 issue 与 roadmap 关联原子能力
3. 将 `flow new` 收紧为纯现场创建
4. 让 `vibe-roadmap` skill 基于这些原子工具完成规划，而不是依赖 shell 隐式编排
