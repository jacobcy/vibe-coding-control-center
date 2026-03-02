---
task_id: "2026-03-02-rotate-alignment"
document_type: task-readme
title: "Rotate Workflow Refinement"
current_layer: "plan"
status: "planning"
author: "Antigravity Agent"
created: "2026-03-02"
last_updated: "2026-03-02"
related_docs:
  - scripts/rotate.sh
  - lib/flow.sh
  - lib/task.sh
  - docs/standards/git-workflow-standard.md
gates:
  scope:
    status: "passed"
    timestamp: "2026-03-02T11:00:00+08:00"
    reason: "Assessed the need to standardize rotate.sh into a first-class vibe command and slash agent action."
  spec:
    status: "pending"
    timestamp: ""
    reason: ""
  plan:
    status: "passed"
    timestamp: "2026-03-02T12:40:00+08:00"
    reason: "Plan v1 updated with in-place rotate, stable directory, and naming-model constraints."
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

# Task: Rotate Workflow Refinement

## 概述
当前在连续多 PR 开发模式下，若不废弃整棵工作树（`vibe flow done`），容易由于 Squash & Merge 的远程机制产生本地旧 commit 污染新功能分支的严重问题。

系统原有的 `scripts/rotate.sh` 能够切出纯正的远程镜像，但它目前是一个游离在 `vibe` 大盘系统外的野脚本，没有与 `vibe new`、`vibe task`、`vibe flow` 形成统一职责。

本任务旨在把“新目录开任务 / 当前目录原地开任务”两种能力收敛回现有命令体系：由 `/vibe-new` 作为智能入口，Shell 命令负责脏活，避免再新增独立的 `/vibe-rotate`。

## 需求澄清

本任务当前新增以下硬约束：

1. **目录默认保持不变**  
   用户希望保留当前 coding agent 的历史对话和工作上下文，因此 rotate 时默认不新建目录、不切换到其他 worktree 路径。

2. **task/worktree 需要原地重绑**  
   rotate 之后，当前目录应继续作为同一棵 worktree 使用，但它绑定的 `current_task`、`.vibe/current-task.json`、共享 registry/worktree 状态都必须切到新任务。

3. **代码基线必须与 PR 后主干一致**  
   在旧任务已经合并的前提下，当前目录内代码需要先对齐 `origin/main`，避免把已完成任务的旧 commit 带进下一次开发。

4. **目录名、分支名、task 必须区分概念**  
   目前这些概念混在一起，导致 rotate 时既不清楚“这个目录是谁在用”，也不清楚“当前在做哪个 task”。

## 推荐方向

- **目录 / worktree label**：保留短、易记、稳定的人类标签，例如 `refactor`、`bug-fix`。它表达“这个目录是干什么用的”，不是 task 真源。
- **agent**：单独表示由谁负责，例如 `claude`、`codex`。
- **task**：统一使用 task registry 中的 `task_id`，例如 `2026-03-02-rotate-alignment`。
- **branch**：必须体现 agent 和 task，例如 `claude/2026-03-02-rotate-alignment`。branch 不再等同于目录标签。
- **git identity**：按 agent 统一生成 `user.name/user.email`，默认只接受常用 agent，特殊值需显式强制。

## 职责收敛结论

- `/vibe-new`：唯一智能入口，负责模式判断与最少交互。
- `vibe task`：任务配置与绑定，最小子命令只保留 `list`、`add`、`update`、`remove`。
- `vibe flow`：流程推进，负责 `start / review / pr / done`，不承担 task 配置面职责。
- `scripts/rotate.sh`：继续作为底层可复用能力存在，但不再暴露为独立 Slash 心智模型。

## 当前状态
- **层级**: Plan
- **状态**: 见 frontmatter `status` 字段（唯一真源）
- **最后更新**: 2026-03-02
- **当前推荐入口**: 用 `/vibe-new` 驱动“当前目录开任务”或“新目录开任务”，底层复用现有 `vibe task` / `vibe flow` / shell 脚本

## 文档导航
- [plan-v1.md](plan-v1.md)
