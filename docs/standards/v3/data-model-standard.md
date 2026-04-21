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
last_updated: 2026-03-24
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
   - GitHub Issues：GitHub issue 真源
   - GitHub Projects：roadmap 规划参考，不作为执行层真源
   - GitHub Pull Requests：PR 真源

## 2. Canonical Tables

### 2.1 SQLite 核心表

高层模型只定义表分层，不重复描述字段细节。表级 schema 以各自标准为准：

#### `flow_state` 表
- **职责**：当前开放 flow 的运行时状态真源
- **主键**：`branch`（TEXT）
- **核心字段**：
  - `flow_slug`：显示名称（V3 中使用，对应原 v2 的 flow name）
  - `status`：现场层状态（`active`/`idle`/`missing`/`stale`）
  - `current_task_id`：当前执行中的 task
  - `created_at`, `updated_at`：时间戳
- **约束**：`branch` 是 PRIMARY KEY，`flow_slug` 是显示名称

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

- **GitHub Issues**：GitHub issue 真源，通过 GitHub API 读写
- **GitHub Projects**：roadmap 规划参考，不作为执行层真源
- **GitHub Pull Requests**：PR 真源，通过 GitHub API 读写

## 3. Layer Ownership

共享状态固定映射如下：

- **SQLite `flow_state` 表** = 执行态（当前开放 flow 的运行时状态真源）
- **SQLite `flow_issue_links` 表** = flow 与 GitHub issue 的关联关系真源
- **SQLite `flow_worktrees` 表** = 开放现场的兼容期 cache / audit hint
- **GitHub Issues** = GitHub issue 外部真源
- **GitHub Projects** = roadmap 规划参考，不作为执行层真源
- **GitHub Pull Requests** = PR 外部真源

补充约束：

- `GitHub issue` 是外部来源对象，不是本地执行对象
- `openspec` 属于执行层输入，不属于规划层来源
- `roadmap item` 仅为历史兼容的 mirror/cache 概念，当前 governance 直接管理 assignee issue，不经过 roadmap item 中间层转换
- GitHub 官方对象语义必须原样保留；项目自定义语义只能作为扩展字段叠加
- `feature` / `task` / `bug` 是 GitHub issue 的 label 分类，当前 governance 直接管理 assignee issue，不经过 roadmap item type 转换
- `task` 是 execution record，不等于 roadmap item 的 `type=task`
- `feature` 不是共享模型字段，只是 `type=feature` 的语义标签或 `flow new <name>` 的命名输入
- `milestone` 属于 roadmap 规划窗口锚点，不属于 flow runtime 字段
- `flow` 只属于执行层，是以 branch 为身份锚点的逻辑交付现场，不承担规划入口语义
- `spec_standard` 是 Vibe 扩展字段，用于标记 execution record 采用的规范体系
- `execution_record_id` 是 Vibe 扩展桥接字段，用于稳定对齐 GitHub Project item 与本地 task
- `spec_standard` / `execution_record_id` / `spec_ref` / `linked_task_ids` 只属于本地执行桥接，不参与 GitHub Project 同步
- `flow new <name>` 中的 `name` 只是现场命名输入，不定义 feature 实体
- `worktrees` 表不再承担开放 flow 的主身份锚点
- `openspec` 不是 roadmap provider
- `feature` 不是共享模型字段
- `dirty` 不是持久化真源字段

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

- GitHub issue 与 flow：多对多（一个 issue 可在不同 flow 中作为 task，一个 flow 可关联多个 issue role）
- GitHub issue 与 task：多对多（task 是 execution bridge，issue 是外部真源）
- roadmap item 与 GitHub issue：历史上为多对多（当前 governance 直接管理 assignee issue，不经过 roadmap item 中间层）
- milestone 与 roadmap item：一对多（规划层概念）
- flow 与 task：一对多
- PR 与 task：一对一
- task 与相关 task：通过 `related_task_ids` 建立关联

补充约束：

- 用户主视角主链是 `GitHub issue -> flow -> plan/spec -> commit -> PR -> done`
- 旧桥接链 `GitHub issue -> roadmap item -> task -> flow` 仅为历史兼容描述，当前 governance 直接管理 assignee issue，不经过 roadmap item 中间层转换
- GitHub issue 与 roadmap item 可以一一映射，也可以多对多关联，取决于 GitHub Project 的组织方式
- roadmap item 与 task 历史上建立关联关系，不共享身份；当前 governance 不依赖此关联
- roadmap item 仅为历史兼容的 mirror/cache 概念，不是 execution record
- 若 task 有多个 `issue_refs`，可指定其中一个作为主闭环 issue；该角色称为 `task issue`
- `ready` / `blocked` / `blockers` 若存在，应作为派生视图而非共享真源持久化字段
- task 是 execution record / execution bridge，不等于 roadmap item 的规划分类
- milestone 只锚定规划窗口，不直接驱动 runtime 切换
- GitHub 官方字段与 Vibe 扩展字段必须可双向同步，且扩展字段不得改写官方对象身份
- task 只允许绑定一个主 PR
- task 不允许跨多个 PR
- task 可以关联多个 issue ref
- `flow` 只属于执行层，不承担规划层关系建模

## 7. Lifecycle Rules

### 7.1 Runtime Binding

- 当前执行中的开放现场应以 `branch` 作为主锚点
- `flow_worktrees` 表只保存当前开放现场的目录容器与 branch 绑定提示，供兼容期查询与审计使用
- `flow_state` 表可以保存当前 runtime 绑定事实，尤其是 `current_task_id`
- task 完成后必须清空 runtime `branch` / `worktree` / `agent` 绑定
- task 归档后必须清空 runtime `branch` / `worktree` / `agent` 绑定
- worktree 删除后必须从 `flow_worktrees` 表移除

### 7.2 Historical Facts

- 未来规划态以 GitHub Projects 为准（通过 API 查询）
- 当前执行态以 `flow_state` 表与 git 现场联合表达，branch 是优先执行锚点；`flow_worktrees` 表只作兼容期辅助提示
- task 的完成与归档事实以 GitHub Project item 状态或本地 task 记录为准
- 已关闭 flow 的历史事实以 GitHub issue/PR 记录为准
- `flow_worktrees` 表只表达当前开放现场，不承担 flow 历史归档

### 7.3 Computed Fields

以下字段只能运行时计算（从 GitHub 或本地关联关系中 hydrate），不能持久化为 `flow_state` 共享真源：

- `task_issue_number`（从 `flow_issue_links` 获取）
- `pr_number`, `pr_ready_for_review`（从 GitHub PR 获取）
- `dirty`
- `ready` / `blocked` / `blockers`（若后续启用）
- 临时统计字段
- 仅用于显示的聚合摘要

## 8. Single-Repo Assumption

本项目按单仓库处理：

- 不在每个 `issue_ref`、`pr_ref`、`source_ref` 内重复保存 `repo`
- 仓库上下文默认来自当前 git remote
- 如未来确有跨仓库需求，只允许在文件根部增加一次 `meta.repo`

## 9. Prohibited Semantics

禁止：

- 在 `flow_state` 中持久化 GitHub 外部真源字段（如 `pr_number`, `pr_ready_for_review`, `task_issue_number`）
- 用 GitHub Projects 记录现场信息（现场信息存 `flow_state` 表）
- 用 `flow_state` 表记录规划优先级
- 用 `flow_worktrees` 表承担历史归档
- 将 `flow_worktrees` 表写成开放 flow 的主身份真源
- 用 GitHub 状态或 `flow_state` 表冒充 flow 关闭历史
- 将 `openspec` 写成 roadmap provider
- 用 Vibe 扩展字段重定义 GitHub 官方对象类型
- 将 `task` 与 roadmap item `type=task` 视为同一对象
- 将 `flow` 回退成规划入口
- 将 `feature` 写成共享模型字段
- 将 `dirty` 写成持久化真源字段
- 将 `worktree_name` / `worktree_path` 当作开放 flow 的主索引
- 将 branch 或 worktree 当作历史唯一索引
- 在各命令或标准中单独发明依赖 gate 语义
- 将 `ready` / `blocked` / `blockers` 持久化为真源字段
