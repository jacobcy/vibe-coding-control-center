---
document_type: artifact
title: Shared State Task 3 Plan Gap
status: open
author: Codex GPT-5
created: 2026-03-10
last_updated: 2026-03-10
related_docs:
  - docs/plans/2026-03-10-shared-state-github-project-alignment-plan.md
  - lib/task_actions.sh
  - lib/task_write.sh
---

# Shared State Task 3 Plan Gap

## Summary

执行 `Shared State GitHub Project Alignment Plan` 的 Task 3 前发现计划落点与当前代码实现不一致。

## Gap

- 计划声明主要修改文件：
  - `lib/task_write.sh`
  - `tests/task/test_task_ops.bats`
  - `tests/task/test_task_helper.zsh`
- 当前真实入口：
  - `vibe task add/update` 的参数解析与字段校验主要在 `lib/task_actions.sh`
  - `lib/task_write.sh` 只负责 registry/worktree/task-file 持久化，不负责 CLI 参数面与非法字段拒绝逻辑

## Why This Blocks Task 3

- Task 3 要实现的内容包含：
  - `task add` 默认写入 `spec_standard/spec_ref`
  - `task update` 支持更新这两个字段
  - 拒绝写入 GitHub item 身份字段
- 这些能力至少部分依赖 `lib/task_actions.sh` 的参数解析与前置校验。
- 若继续严格按当前计划执行，会出现“改了 persistence 层但 CLI 入口仍不支持”的半完成状态。

## Required Plan Fix

- 在 Task 3 的 `Files To Modify` 中补入 `lib/task_actions.sh`
- 明确区分：
  - 参数解析与非法字段拒绝：`lib/task_actions.sh`
  - 持久化：`lib/task_write.sh`
  - 查询输出：`lib/task_query.sh`（属于 Task 4）

## Status

- Task 1: completed
- Task 2: completed
- Task 3: blocked by plan gap before implementation
