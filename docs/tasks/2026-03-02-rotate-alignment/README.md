---
task_id: "2026-03-02-rotate-alignment"
document_type: task-readme
title: "Rotate Workflow Refinement"
current_layer: "plan"
status: "todo"
author: "Antigravity Agent"
created: "2026-03-02"
last_updated: "2026-03-02"
related_docs:
  - scripts/rotate.sh
  - lib/flow.sh
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
    timestamp: "2026-03-02T11:00:00+08:00"
    reason: "Plan v1 defined for integrating rotate into vibe flow and creating a slash proxy."
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

系统原有的 `scripts/rotate.sh` 能够切出纯正的远程镜像，但它目前是一个游离在 `vibe` 大盘系统外的野脚本，没有享受与其他 `vibe flow` 成员同等的终端权限和智能拦截功能，也不支持直接被 Slash 唤起。

本任务旨在通过引入 `/vibe-rotate` 和重构 `vibe flow rotate` 真正地把这个断代回滚机制升级为大满贯核心武器。

## 当前状态
- **层级**: Plan
- **状态**: Todo
- **最后更新**: 2026-03-02

## 文档导航
- [plan-v1.md](plan-v1.md)
