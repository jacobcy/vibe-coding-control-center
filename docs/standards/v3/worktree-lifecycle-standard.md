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
last_updated: 2026-03-09
related_docs:
  - SOUL.md
  - CLAUDE.md
  - docs/standards/glossary.md
  - docs/standards/action-verbs.md
  - docs/standards/v3/git-workflow-standard.md
  - docs/standards/v3/command-standard.md
---

# Worktree Lifecycle Standard

本文档定义 `worktree` 的物理生命周期规则，只回答目录现场如何创建、复用、清理与回收，以及 flow 关闭后目录与历史如何分离。

`flow`、`workflow`、`worktree`、`branch` 的正式术语以 [glossary.md](/Users/jacobcy/src/vibe-center/wt-claude-v3/docs/standards/glossary.md) 为准。交付流程语义见 [git-workflow-standard.md](/Users/jacobcy/src/vibe-center/wt-claude-v3/docs/standards/v3/git-workflow-standard.md)。

## 1. Scope

本文档只定义：

- `worktree` 的物理角色
- 何时新建目录，何时复用目录
- 何时清理目录
- 现场残留与幽灵目录的治理规则
- flow 关闭后目录、branch 与历史留存的关系

本文档不定义：

- `roadmap -> task -> flow -> pr` 的业务推进流程
- Python CLI 自动化细节
- 共享状态 schema
- manager agent / orchestra agent 如何决定是否进入 plan、run、review 等步骤

## 2. Core Model

- `worktree` 是物理目录容器
- `branch` 是该目录当前承载的 Git 提交线
- `flow` 可以借由该目录承载，但不等于该目录

因此：

- 新 `flow` 不强制要求新 `worktree`
- 复用同一目录承载新的 `flow` 是允许的
- 但复用目录时，必须显式切换到新的 `branch`
- 当前开放 flow 的执行判断应优先围绕 `branch`，`worktree` 只提供目录 hint
- 复用目录进入新的逻辑 `flow` 时，应通过 `git checkout` 切换分支，并运行 `vibe3 flow update` 注册现场，而不是靠目录名暗示
- 已关闭 flow 的历史不保存在 `worktree` 目录内，而应保存在共享历史真源中

补充边界：

- `manager` 模块负责提供 worktree 的创建、查找、复用、回收能力
- 是否调用这些能力，由 manager agent、orchestra agent 或其他 skill 根据现场决定
- worktree 模块本身不应隐藏“发现异常就自动推进后续流程”的业务判断

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
- 目标 flow 仍处于 `open + no_pr`

复用目录时的最低要求：

- 当前 `flow` 语义已经结束或冻结
- 当前目录切到新的 `branch`
- 新目录语义只服务一个新的当前交付目标
- 当前目录的 flow runtime 记录已同步到新的 `branch` / `flow` 语义，且 `branch` 是主锚点
- 若目标 flow 已有 PR 事实，不得通过目录复用继续切换

## 4. Residual Changes

当目录中仍有未提交改动时：

- 若这些改动属于当前 `pr` 的 follow-up，可以保留在当前目录继续处理
- 若这些改动属于新的交付目标，应在切换 `branch` 后继续处理；通过 `/vibe-new (skill)` 启动新 flow 时，默认应根据用户选择安全带入或暂存这批未提交改动

禁止：

- 让同一批未提交改动同时服务两个当前交付目标
- 在目录语义已经切换后，继续按旧 `flow` 理解这些改动

## 5. Rotate-Style Reuse

允许存在"目录不变、`branch` 变化"的过渡模式。

该模式的语义是：

- 复用同一个 `worktree`
- 将当前未提交改动带入新的 `branch`
- 让该目录开始承载新的 `flow`
- 标准入口应是 `git checkout -b <new-branch>` 后跟 `vibe3 flow update`；或者通过 `/vibe-new (skill)` 自动化流程
- 只允许进入尚未关闭、且尚未发过 PR 的 flow

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

补充规则：

- `vibe3 flow update` 用于注册或更新活跃分支的现场事实
- 若要关闭现场，应通过 `git branch -d` 删除分支
- 不再提供 `vibe3 flow done` 等生命周期封装，流程收口由 `/vibe-done (skill)` 编排
- flow 关闭后，目录可以被保留或复用，但不能继续代表旧 flow；同一目录可直接继续 `vibe3 flow update` 注册新分支现场，不要求切换物理 worktree
- 即使 branch 被删除，已关闭 flow 的历史也必须保留
- manager 模块可以提供 branch / worktree 回收入口，但是否在某一时刻回收，属于编排层判断

## 7. Ghost Worktree and Ghost Branch

出现下列情况应视为异常：

- 目录仍在，但不再对应任何当前 `flow`
- `branch` 已失去交付语义，却仍被当作活跃现场使用
- `pr` 已结束，但目录仍继续以旧交付目标名义累积新改动

恢复原则：

- 先判断目录是否仍有当前用途
- 若仍有用途，则切到新的 `branch` 与新的 `flow` 语义
- 若无用途，则清理目录

补充要求：

- worktree 脏现场、幽灵目录或异常 branch 的修复，应由 orchestrator、manager agent 或专门 skill 调用能力层完成
- 不应要求 worktree 模块独自承担“自我诊断并自动恢复完整业务流程”的职责

若 branch 已经产生过 PR 事实但 flow 尚未关闭：

- 该目录不应再作为普通开发 worktree 继续 `switch`
- 应转交 skill 做整合或收口，而不是让 Python CLI 自动修复

## 8. Relationship With Delivery Workflow

`worktree` 生命周期必须服从交付流程，而不能反过来主导交付语义。

因此：

- 不应因为目录没变，就假设当前 `flow` 没变
- 不应因为目录还在，就继续沿用旧 `pr` 目标
- `flow` 的变化应先由交付目标决定，再决定是否复用目录
- `worktree` 被清理或 branch 被删除，不等于 flow 历史可以丢失
