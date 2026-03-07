---
document_type: standard
title: Shared Data Model Standard
status: approved
scope: shared-state
authority:
  - data-model-schema
  - shared-state-files
  - entity-relationships
  - state-lifecycle
author: Codex GPT-5
created: 2026-03-08
last_updated: 2026-03-08
related_docs:
  - SOUL.md
  - CLAUDE.md
  - STRUCTURE.md
  - docs/README.md
  - docs/standards/command-standard.md
  - docs/standards/registry-json-standard.md
  - docs/standards/roadmap-json-standard.md
---

# 共享数据模型标准

本文档是 Vibe 共享状态数据模型的高层规范真源，定义 `roadmap.json`、`registry.json`、`worktrees.json` 的职责边界、命名规则、关系约束和生命周期规则。

本文档只定义最终标准，不记录讨论过程、迁移步骤或实现现状。文件级精确 schema 见：

- [registry-json-standard.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/registry-json-standard.md)
- [roadmap-json-standard.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/roadmap-json-standard.md)

## 1. Scope

本文档只覆盖三类共享状态文件：

- `roadmap.json`
- `registry.json`
- `worktrees.json`

命令语义由 [command-standard.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/command-standard.md) 定义；本文只负责数据模型本身。

## 2. Canonical Files

### 2.1 `roadmap.json`

`roadmap.json` 是规划态真源，只负责：

- roadmap item
- 规划状态
- `version_goal`
- roadmap item 与 issue / task 的映射

`roadmap.json` 不负责：

- branch
- worktree
- dirty
- task runtime
- PR 历史
- 本地 `epic` / `milestone` 派生模型

### 2.2 `registry.json`

`registry.json` 是执行态真源，只负责：

- task 生命周期
- task 与 roadmap item / issue / PR 的关联
- subtasks
- task 当前 runtime 绑定事实
- task 最终归档事实

`registry.json` 不负责：

- 规划优先级
- 现场创建与销毁
- 长期 worktree 历史
- 多个 PR 历史数组
- 把 branch / worktree 当作历史索引

### 2.3 `worktrees.json`

`worktrees.json` 是现场态真源，只负责：

- 当前存在的 worktree
- 当前 worktree 的 path、branch、agent、绑定 task
- 当前现场状态

`worktrees.json` 不负责：

- 历史查询
- 已删除 worktree 的长期记录
- task 归档事实
- roadmap 规划状态
- 持久化 `dirty`

## 3. Layer Ownership

三层共享状态固定映射如下：

- `roadmap.json` = 规划态
- `registry.json` = 执行态
- `worktrees.json` = 现场态

补充约束：

- `openspec` 属于执行层输入，不属于规划层来源
- `feature` 不是共享模型字段，只是 `flow new <name>` 的命名输入

## 4. Naming Rules

### 4.1 Field Naming

- 字段统一使用 `snake_case`
- 主键字段统一为 `<entity>_id`
- 多值 ID 字段统一为 `<entity>_ids`
- 多值引用字段统一为 `<entity>_refs`
- 时间字段统一为 `*_at`

示例：

- `roadmap_item_id`
- `task_id`
- `current_task_id`
- `issue_refs`
- `related_task_ids`
- `created_at`
- `updated_at`

### 4.2 Status Naming

禁止用单个模糊字段混装不同层语义。

规划层状态只允许：

- `p0`
- `current`
- `next`
- `deferred`
- `rejected`

执行层状态只允许：

- `todo`
- `in_progress`
- `blocked`
- `completed`
- `archived`

现场层状态只允许：

- `active`
- `idle`
- `missing`
- `stale`

禁止：

- `in-progress`
- `done`
- `merged`
- `skipped`
- 用模糊字段 `state` 混装不同层状态

## 5. Identity Rules

- `roadmap_item_id` 是 roadmap item 的独立主键
- `task_id` 是 task 的独立主键
- `worktree_name` 不是历史唯一标识
- `branch` 不是历史唯一标识

同一实体只能有一个主键真源，禁止同时维护等价的别名主键。

## 6. Relationship Rules

允许的实体关系如下：

- issue 与 roadmap item：多对多
- issue 与 task：多对多
- roadmap item 与 task：多对多
- PR 与 task：一对一
- task 与相关 task：通过 `related_task_ids` 建立关联

补充约束：

- task 只允许绑定一个主 PR
- task 不允许跨多个 PR
- roadmap item 可以关联多个 task
- task 可以关联多个 issue ref

## 7. Lifecycle Rules

### 7.1 Runtime Binding

- 当前执行中的现场绑定以 `worktrees.json` 为准
- `registry.json` 可以保存当前 runtime 绑定事实
- task 完成后必须清空 runtime `branch` / `worktree` / `agent` 绑定
- task 归档后必须清空 runtime `branch` / `worktree` / `agent` 绑定
- worktree 删除后必须从 `worktrees.json` 移除

### 7.2 Historical Facts

- 未来规划态以 `roadmap.json` 为准
- 当前执行态以 `registry.json` 与 `worktrees.json` 联合表达
- 历史完成态以 `registry.json` 的完成与归档事实为准

### 7.3 Computed Fields

以下字段只能运行时计算，不能持久化为共享真源：

- `dirty`
- 临时统计字段
- 仅用于显示的聚合摘要

## 8. Single-Repo Assumption

本项目按单仓库处理：

- 不在每个 `issue_ref`、`pr_ref`、`source_ref` 内重复保存 `repo`
- 仓库上下文默认来自当前 git remote
- 如未来确有跨仓库需求，只允许在文件根部增加一次 `meta.repo`

## 9. Prohibited Semantics

禁止：

- 用 `roadmap.json` 记录现场信息
- 用 `registry.json` 记录规划优先级
- 用 `worktrees.json` 承担历史归档
- 将 `openspec` 写成 roadmap provider
- 将 `feature` 写成共享模型字段
- 将 `dirty` 写成持久化真源字段
- 将 branch 或 worktree 当作历史唯一索引
