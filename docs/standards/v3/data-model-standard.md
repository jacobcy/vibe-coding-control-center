---
document_type: standard
title: Shared Data Model Standard
status: approved
scope: shared-state
authority:
  - data-model-schema
  - shared-state-tables
  - entity-relationships
  - state-lifecycle
author: Codex GPT-5
created: 2026-03-08
last_updated: 2026-06-03
related_docs:
  - SOUL.md
  - CLAUDE.md
  - STRUCTURE.md
  - docs/README.md
  - docs/standards/glossary.md
  - docs/standards/v3/command-standard.md
  - docs/standards/v3/database-schema-standard.md
---

# 共享数据模型标准

本文档是 Vibe Center v3 共享状态数据模型的高层规范真源，定义 SQLite 数据表（`flow_state`、`flow_issue_links` 等）的职责边界、命名规则、关系约束和生命周期规则，以及 GitHub 作为外部真源的交互边界。

本文档只定义高层数据模型边界，不重复定义表级 schema，不记录讨论过程、迁移步骤或实现现状。表级精确 schema 见：

- [database-schema-standard.md](database-schema-standard.md)

本文档涉及的 `GitHub issue`、`roadmap item`、`task`、`flow`、`worktree`、`branch` 等正式术语以 [glossary.md](glossary.md) 为准。

## 1. Scope

本文档覆盖两类共享状态存储：

1. **SQLite 本地共享状态**（`.git/vibe3/handoff.db`）
   - `flow_state` 表：当前开放 flow 的运行时状态
   - `flow_issue_links` 表：flow 与 GitHub issue 的关联关系
   - `flow_worktrees` 表：worktree 与 flow 的绑定关系（兼容期）
   - `task_execution` 表：task 执行记录（V3 暂不实现，预留）

2. **GitHub 外部真源**
   - GitHub Issues：GitHub issue 真源，作为执行驱动的核心。
   - GitHub Projects：作为 **Roadmap 规划参考**，不作为执行层真源。
   - GitHub Pull Requests：PR 真源

## 2. Canonical Tables

### 2.1 SQLite 核心表

高层模型只定义表分层，不重复描述字段细节。表级 schema 以各自标准为准：

#### `flow_state` 表
- **职责**：当前开放 flow 的运行时状态真源
- **主键**：`branch`（TEXT）
- **核心字段**：
  - `flow_slug`：显示名称
  - `flow_status`：执行状态（`active`/`blocked`/`done`/`stale`/`aborted`）
  - `blocked_by_issue`：阻塞当前 flow 的 issue 编号
  - `blocked_reason`：阻塞原因文本
  - `transition_count`：状态流转计数（用于防死循环）
  - `spec_ref`, `plan_ref`, `report_ref`, `audit_ref`, `indicate_ref`：各阶段文档引用
  - `planner_actor`, `executor_actor`, `reviewer_actor`, `manager_actor`：各角色执行者
  - `created_at`, `updated_at`：时间戳
- **约束**：`branch` 是 PRIMARY KEY，`flow_status` 必须符合 canonical 枚举

#### `flow_issue_links` 表
- **职责**：flow 与 GitHub issue 的多对多关联关系
- **主键**：`branch` + `issue_number`（复合主键）
- **核心字段**：
  - `branch`：flow 的 branch 名称
  - `issue_number`：GitHub issue 编号
  - `is_primary`：是否为主要关联 issue
  - `linked_at`：关联时间

#### `flow_worktrees` 表（兼容期）
- **职责**：worktree 与 flow 的绑定关系，兼容期辅助提示
- **核心字段**：
  - `branch`：flow 的 branch 名称
  - `worktree_path`：worktree 目录路径
  - `worktree_name`：worktree 名称（兼容 v2）

### 2.2 GitHub 外部真源

- **GitHub Issues**：GitHub issue 真源，由 Orchestra 直接分诊并由 Assignee 驱动。
- **GitHub Projects**：作为 Roadmap 规划与优先级参考，不作为执行状态的真源。
- **GitHub Pull Requests**：PR 真源，通过 GitHub API 读写

## 3. Layer Ownership

共享状态固定映射如下：

- **SQLite `flow_state` 表** = 执行态（当前开放 flow 的运行时状态真源）
- **SQLite `flow_issue_links` 表** = flow 与 GitHub issue 的关联关系真源
- **SQLite `flow_worktrees` 表** = 开放现场的兼容期 cache / audit hint
- **GitHub Issues** = GitHub issue 外部真源（执行驱动源）
- **GitHub Projects** = Roadmap 规划参考
- **GitHub Pull Requests** = PR 外部真源

补充约束：

- `GitHub issue` 是外部来源对象，是执行主线的起点。
- `openspec` 属于执行层输入，不属于规划层来源。
- `roadmap item` 为历史兼容的规划概念。当前 **direct-assignee governance** 模式直接管理 GitHub issue 及其分配（assignee），不再依赖 `roadmap item` 作为中间层。
- GitHub 官方对象语义必须原样保留；项目自定义语义只能作为扩展字段叠加。
- `feature` / `task` / `bug` 是 GitHub issue 的 label 分类，驱动不同角色（planner/executor/etc.）的行为。
- `task` 在 V3 中指代本地执行记录（execution record），不再等同于 V2 的 `roadmap item type=task`。
- `flow` 仅属于执行层，是物理或逻辑现场的身份锚点，不承担规划入口语义。
- `spec_standard` / `execution_record_id` / `spec_ref` / `linked_task_ids` 只属于本地执行桥接。
- `worktrees` 表不再承担开放 flow 的主身份锚点。
- `dirty` 不属于持久化共享真源。

## 4. Naming Rules

### 4.1 Field Naming

- 字段统一使用 `snake_case`
- 主键字段统一为 `<entity>_id`
- 多值 ID 字段统一为 `<entity>_ids`
- 多值引用字段统一为 `<entity>_refs`
- 时间字段统一为 `*_at`

示例：

- `task_id`
- `current_task_id`
- `issue_refs`
- `related_task_ids`
- `created_at`
- `updated_at`

### 4.2 Status Naming

禁止用单个模糊字段混装不同层语义。

规划层状态（Roadmap/Project）只允许：

- `p0`
- `current`
- `next`
- `deferred`
- `rejected`

执行层状态（GitHub Issue/Task）只允许：

- `todo`
- `in_progress`
- `blocked`
- `completed`
- `archived`

现场层状态（Flow Runtime）只允许：

- `active`
- `blocked`
- `done"
- `stale`
- `aborted`

禁止：

- `idle`
- `missing`
- `merged`
- `in-progress`
- `done` (作为规划层状态时禁止)
- `skipped`
- 用模糊字段 `state` 混装不同层状态

## 5. Identity Rules

- `task_id` 是本地执行记录的独立主键。
- `branch` 是当前开放现场（Flow）的主要索引。
- `worktree_name` 不是历史唯一标识。

同一实体只能有一个主键真源，禁止同时维护等价的别名主键。

## 6. Relationship Rules

允许的实体关系如下：

- GitHub issue 与 flow：多对多（一个 issue 可在不同 flow 中作为 task，一个 flow 可关联多个 issue role）。
- GitHub issue 与 task：多对多（task 是 execution bridge，issue 是外部真源）。
- milestone 与 GitHub issue：一对多（规划层与执行源的关联）。
- flow 与 task：一对多。
- PR 与 task：一对一。
- task 与相关 task：通过 `related_task_ids` 建立关联。

补充约束：

- 用户主视角主链是 `GitHub issue -> flow -> plan/spec -> commit -> PR -> done`。
- 旧桥接链 `GitHub issue -> roadmap item -> task -> flow` 已退役。当前治理直接作用于 GitHub issue 分配。
- `roadmap item` 概念仅保留在规划层参考中。
- `ready` / `blocked` / `blockers` 若存在，应作为派生视图而非共享真源持久化字段。
- GitHub 官方字段与 Vibe 扩展字段必须可双向同步。
- task 只允许绑定一个主 PR。
- `flow` 仅属于执行层，不承担规划层关系建模。

## 7. Lifecycle Rules

### 7.1 Runtime Binding

- 当前执行中的开放现场应以 `branch` 作为主锚点。
- `flow_worktrees` 表只保存当前开放现场的目录容器与 branch 绑定提示。
- `flow_state` 表保存当前 runtime 状态事实。
- task 完成或归档后，必须清理相关的现场绑定。

### 7.2 Historical Facts

- 规划态以 GitHub Projects 为准。
- 执行态以 `flow_state` 表与 git 现场联合表达。
- 已关闭 flow 的历史事实以 GitHub issue/PR 记录为准。

### 7.3 Computed Fields

以下字段只能运行时计算，不能持久化为 `flow_state` 共享真源：

- `task_issue_number`（从 `flow_issue_links` 获取）
- `pr_number`（从 GitHub PR 获取）
- `dirty`
- `ready` / `blocked` / `blockers`
- 仅用于显示的聚合摘要

## 8. Single-Repo Assumption

本项目按单仓库处理：

- 仓库上下文默认来自当前 git remote。
- 不在每个引用内重复保存 `repo`。

## 9. Prohibited Semantics

禁止：

- 在 `flow_state` 中持久化 GitHub 外部真源字段（如 `pr_number`）。
- 用 GitHub Projects 记录实时现场信息。
- 用 `flow_worktrees` 表承担历史归档。
- 将 `flow_worktrees` 写成开放 flow 的唯一主索引。
- 用 Vibe 扩展字段重定义 GitHub 官方对象类型。
- 将 `feature` 写成核心持久化数据模型字段（它仅是 label 或命名输入）。
- 将 `dirty` 写成持久化真源字段。
- 在各标准中单独发明冲突的依赖 gate 语义。
