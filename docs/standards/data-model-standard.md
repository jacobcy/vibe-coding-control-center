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
last_updated: 2026-03-10
related_docs:
  - SOUL.md
  - CLAUDE.md
  - STRUCTURE.md
  - docs/README.md
  - docs/standards/glossary.md
  - docs/standards/command-standard.md
  - docs/standards/registry-json-standard.md
  - docs/standards/roadmap-json-standard.md
---

# 共享数据模型标准

本文档是 Vibe 共享状态数据模型的高层规范真源，定义 `roadmap.json`、`registry.json`、`worktrees.json`、`flow-history.json` 的职责边界、命名规则、关系约束和生命周期规则。

本文档只定义高层数据模型边界，不重复定义文件级 schema，不记录讨论过程、迁移步骤或实现现状。文件级精确 schema 见：

- [registry-json-standard.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/registry-json-standard.md)
- [roadmap-json-standard.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/roadmap-json-standard.md)

本文档涉及的 `repo issue`、`roadmap item`、`task`、`flow`、`worktree`、`branch` 等正式术语以 [glossary.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/glossary.md) 为准。

## 1. Scope

本文档只覆盖四类共享状态文件：

- `roadmap.json`
- `registry.json`
- `worktrees.json`
- `flow-history.json`

命令语义由 [command-standard.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/command-standard.md) 定义；本文只负责数据模型本身。

## 2. Canonical Files

高层模型只定义文件分层，不重复描述文件内部字段。文件级 schema 以各自标准为准：

- `roadmap.json`
  - 规划态真源
  - schema 见 [roadmap-json-standard.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/roadmap-json-standard.md)
- `registry.json`
  - 执行态真源
  - schema 见 [registry-json-standard.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/registry-json-standard.md)
- `worktrees.json`
  - 现场态真源
  - 本文当前只定义其高层职责边界，尚无单独文件级 schema 标准
- `flow-history.json`
  - flow 历史真源
  - 记录已关闭 flow 的墓碑事实，不承担当前运行态

## 3. Layer Ownership

共享状态固定映射如下：

- `roadmap.json` = 规划态（mirrored GitHub Project item 的本地真源）
- `registry.json` = 执行态（task execution record 真源）
- `worktrees.json` = 现场态（flow runtime 真源）
- `flow-history.json` = 已关闭 flow 的历史态

补充约束：

- `repo issue` 是外部来源对象，不是本地执行对象
- `openspec` 属于执行层输入，不属于规划层来源
- `roadmap item` 是 mirrored `GitHub Project item`
- GitHub 官方对象语义必须原样保留；项目自定义语义只能作为扩展字段叠加
- `roadmap.json.project_id` 是当前仓库默认 GitHub Project 身份锚点
- `feature` / `task` / `bug` 在规划层默认解释为 roadmap item `type`
- `task` 是 execution record，不等于 roadmap item 的 `type=task`
- `feature` 不是共享模型字段，只是 `type=feature` 的语义标签或 `flow new <name>` 的命名输入
- `milestone` 属于 roadmap 规划窗口锚点，不属于 registry 或 worktree runtime 字段
- `flow` 只属于执行层，是 task 的运行时容器，不承担规划入口语义
- `spec_standard` 是 Vibe 扩展字段，用于标记 execution record 采用的规范体系
- `execution_record_id` 是 Vibe 扩展桥接字段，用于稳定对齐 GitHub Project item 与本地 task
- `spec_standard` / `execution_record_id` / `spec_ref` / `linked_task_ids` 只属于本地执行桥接，不参与 GitHub Project 同步
- `flow new <name>` 中的 `name` 只是现场命名输入，不定义 feature 实体

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

- repo issue 与 roadmap item：多对多
- repo issue 与 task：多对多
- roadmap item 与 task：多对多
- milestone 与 roadmap item：一对多
- flow 与 task：一对多
- PR 与 task：一对一
- task 与相关 task：通过 `related_task_ids` 建立关联

补充约束：

- 用户主视角主链是 `repo issue -> flow -> plan/spec -> commit -> PR -> done`
- 内部桥接链保留为 `repo issue -> roadmap item -> task -> flow`
- `repo issue` 与 roadmap item 可以一一映射，也可以多对多关联，取决于 GitHub Project 的组织方式
- roadmap item 与 task 只建立关联关系，不共享身份
- roadmap item 是 mirrored GitHub Project item，不是 execution record
- `type=task` 只表示 roadmap item 的规划分类，不表示本地 execution record 本体
- task 是 execution record / execution bridge，不等于 GitHub Project `type=task` item 本体
- milestone 只锚定规划窗口，不直接驱动 runtime 切换
- GitHub 官方字段与 Vibe 扩展字段必须可双向同步，且扩展字段不得改写官方对象身份
- task 只允许绑定一个主 PR
- task 不允许跨多个 PR
- roadmap item 可以关联多个 task
- 一个 `type=feature` 的 roadmap item 可以关联多个 `task` execution record
- roadmap item 是 planning 中间层，task 是 flow 建立后的 execution bridge
- task 可以关联多个 issue ref
- `flow` 只属于执行层，不承担规划层关系建模

## 7. Lifecycle Rules

### 7.1 Runtime Binding

- 当前执行中的开放现场应以 `branch` 作为主锚点
- `worktrees.json` 保存当前开放现场的目录容器与 branch 绑定提示
- `registry.json` 可以保存当前 runtime 绑定事实，尤其是 `runtime_branch`
- task 完成后必须清空 runtime `branch` / `worktree` / `agent` 绑定
- task 归档后必须清空 runtime `branch` / `worktree` / `agent` 绑定
- worktree 删除后必须从 `worktrees.json` 移除

### 7.2 Historical Facts

- 未来规划态以 `roadmap.json` 为准
- 当前执行态以 `registry.json` 与 `worktrees.json` 联合表达，但 branch 是优先执行锚点
- task 的完成与归档事实以 `registry.json` 为准
- 已关闭 flow 的历史事实以 `flow-history.json` 为准
- `worktrees.json` 只表达当前开放现场，不承担 flow 历史归档

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
- 用 `registry.json` 或 `worktrees.json` 冒充 flow 关闭历史
- 将 `openspec` 写成 roadmap provider
- 用 Vibe 扩展字段重定义 GitHub 官方对象类型
- 将 `task` 与 roadmap item `type=task` 视为同一对象
- 将 `flow` 回退成规划入口
- 将 `feature` 写成共享模型字段
- 将 `dirty` 写成持久化真源字段
- 将 `worktree_name` / `worktree_path` 当作开放 flow 的主索引
- 将 branch 或 worktree 当作历史唯一索引
