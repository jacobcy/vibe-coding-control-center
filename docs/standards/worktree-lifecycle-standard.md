---
document_type: standard
title: Worktree Lifecycle Standard
status: active
scope: worktree-lifecycle
authority:
  - worktree-usage
  - worktree-reuse
  - worktree-cleanup
author: Codex GPT-5
created: 2026-03-08
last_updated: 2026-03-08
related_docs:
  - SOUL.md
  - CLAUDE.md
  - docs/standards/glossary.md
  - docs/standards/action-verbs.md
  - docs/standards/git-workflow-standard.md
  - docs/standards/command-standard.md
---

# Worktree Lifecycle Standard

本文档定义 `worktree` 的物理生命周期规则，只回答目录现场如何创建、复用、清理与回收。

`flow`、`workflow`、`worktree`、`branch` 的正式术语以 [glossary.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/glossary.md) 为准。交付流程语义见 [git-workflow-standard.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/git-workflow-standard.md)。

## 1. Scope

本文档只定义：

- `worktree` 的物理角色
- 何时新建目录，何时复用目录
- 何时清理目录
- 现场残留与幽灵目录的治理规则

本文档不定义：

- `roadmap -> task -> flow -> pr` 的业务推进流程
- shell 自动化细节
- 共享状态 schema

## 2. Core Model

- `worktree` 是物理目录容器
- `branch` 是该目录当前承载的 Git 提交线
- `flow` 可以借由该目录承载，但不等于该目录

因此：

- 新 `flow` 不强制要求新 `worktree`
- 复用同一目录承载新的 `flow` 是允许的
- 但复用目录时，必须显式切换到新的 `branch`
- 复用目录进入新的逻辑 `flow` 时，应通过正式 flow 切换能力完成，而不是靠目录名暗示

## 3. Create and Reuse Rules

### 3.1 Create a New Worktree

以下情况优先新建 `worktree`：

- 需要与当前目录完全隔离
- 需要保留当前目录的未提交状态不受影响
- 需要并行推进多个独立交付目标

### 3.2 Reuse the Current Worktree

以下情况允许复用当前 `worktree`：

- 当前目录只需要承载下一个 `flow`
- 旧 `flow` 已停止继续扩展
- 当前目录中的未提交改动需要被带入新的 `branch`

复用目录时的最低要求：

- 当前 `flow` 语义已经结束或冻结
- 当前目录切到新的 `branch`
- 新目录语义只服务一个新的当前交付目标
- 当前目录的 flow runtime 记录已同步到新的 `branch` / `flow` 语义

## 4. Residual Changes

当目录中仍有未提交改动时：

- 若这些改动属于当前 `pr` 的 follow-up，可以保留在当前目录继续处理
- 若这些改动属于新的交付目标，应在切换 `branch` 后继续处理

禁止：

- 让同一批未提交改动同时服务两个当前交付目标
- 在目录语义已经切换后，继续按旧 `flow` 理解这些改动

## 5. Rotate-Style Reuse

允许存在“目录不变、`branch` 变化”的过渡模式。

该模式的语义是：

- 复用同一个 `worktree`
- 将当前未提交改动带入新的 `branch`
- 让该目录开始承载新的 `flow`
- 标准入口应是显式的 flow 切换命令；游离脚本只能作为兼容包装存在

该模式不是：

- 让旧 `flow` 继续承担新的交付目标
- 让一个目录同时保留两个当前 `flow` 身份

## 6. Cleanup Rules

以下情况应清理当前 `worktree`：

- 当前 `flow` 已完成且目录无后续用途
- 当前 `flow` 已废弃且目录不再需要保留现场
- 已确认目录属于幽灵目录或失效目录

清理目标：

- 目录不再承载当前 `flow`
- 不再残留错误的当前 `branch` 语义
- 不再形成幽灵目录、幽灵分支、僵尸现场

## 7. Ghost Worktree and Ghost Branch

出现下列情况应视为异常：

- 目录仍在，但不再对应任何当前 `flow`
- `branch` 已失去交付语义，却仍被当作活跃现场使用
- `pr` 已结束，但目录仍继续以旧交付目标名义累积新改动

恢复原则：

- 先判断目录是否仍有当前用途
- 若仍有用途，则切到新的 `branch` 与新的 `flow` 语义
- 若无用途，则清理目录

## 8. Relationship With Delivery Workflow

`worktree` 生命周期必须服从交付流程，而不能反过来主导交付语义。

因此：

- 不应因为目录没变，就假设当前 `flow` 没变
- 不应因为目录还在，就继续沿用旧 `pr` 目标
- `flow` 的变化应先由交付目标决定，再决定是否复用目录
