---
document_type: standard
title: Registry JSON Standard
status: approved
scope: shared-state
authority:
  - registry-json-schema
  - task-registry-fields
author: Codex GPT-5
created: 2026-03-08
last_updated: 2026-03-10
related_docs:
  - SOUL.md
  - CLAUDE.md
  - docs/standards/glossary.md
  - docs/standards/data-model-standard.md
  - docs/standards/command-standard.md
---

# `registry.json` 标准

本文档定义 `registry.json` 的最终文件结构。它是执行态共享真源，只表达 task execution record 注册信息，不表达规划层或现场层以外的内容。

本文档涉及的 `task`、`repo issue`、`roadmap item`、`worktree`、`branch`、`pr` 等正式术语以 [glossary.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/glossary.md) 为准。

## 1. File Responsibility

`registry.json` 只负责：

- task 主记录（execution record）
- task 生命周期状态
- task 与 roadmap / repo issue / PR 的关联
- task 采用的 spec 标准与规范引用
- task subtasks
- task 当前 runtime 绑定事实
- task 完成与归档事实

`registry.json` 不负责：

- GitHub Project item 本体
- roadmap item `type` 定义
- roadmap 规划优先级
- version goal
- worktree 历史
- `dirty`
- 多 PR 历史数组

## 2. Root Shape

根对象固定为：

```json
{
  "schema_version": "v2",
  "tasks": []
}
```

根对象只允许：

- `schema_version`
- `tasks`

禁止：

- 在根对象写入 `roadmap`
- 在根对象写入 `worktrees`
- 在根对象写入规划态统计字段

## 3. Task Shape

每个 task 对象固定包含以下字段：

```json
{
  "task_id": "2026-03-08-command-standard-rewrite",
  "title": "Rewrite command standard",
  "description": "Replace obsolete command spec with shared-state command standard.",
  "status": "in_progress",
  "source_type": "local",
  "source_refs": [],
  "spec_standard": "openspec",
  "spec_ref": "openspec/changes/command-standard",
  "roadmap_item_ids": [
    "roadmap-command-standard"
  ],
  "issue_refs": [],
  "pr_ref": null,
  "related_task_ids": [],
  "current_subtask_id": null,
  "subtasks": [],
  "runtime_worktree_name": "wt-claude-refactor",
  "runtime_worktree_path": "/path/to/wt-claude-refactor",
  "runtime_branch": "claude/refactor",
  "runtime_agent": "claude",
  "next_step": "Rewrite docs/standards/command-standard.md",
  "created_at": "2026-03-08T10:00:00+08:00",
  "updated_at": "2026-03-08T10:30:00+08:00",
  "completed_at": null,
  "archived_at": null
}
```

## 4. Field Rules

### 4.1 Required Fields

以下字段必须存在：

- `task_id`
- `title`
- `status`
- `source_type`
- `source_refs`
- `spec_standard`
- `spec_ref`
- `roadmap_item_ids`
- `issue_refs`
- `related_task_ids`
- `subtasks`
- `created_at`
- `updated_at`

### 4.2 Optional or Nullable Fields

以下字段允许为 `null`：

- `description`
- `spec_ref`
- `pr_ref`
- `current_subtask_id`
- `runtime_worktree_name`
- `runtime_worktree_path`
- `runtime_branch`
- `runtime_agent`
- `next_step`
- `completed_at`
- `archived_at`

### 4.3 Status Enum

`status` 只允许：

- `todo`
- `in_progress`
- `blocked`
- `completed`
- `archived`

### 4.4 Source Enum

`source_type` 只允许：

- `issue`
- `local`
- `openspec`

`source_type` 表示 execution record 的创建来源，不表示 GitHub Project item 类型：

- `issue` = 由 `repo issue` 驱动创建
- `local` = 由本地执行决策创建
- `openspec` = 由 OpenSpec 执行输入创建

### 4.5 Spec Standard Enum

`spec_standard` 只允许：

- `openspec`
- `kiro`
- `superpowers`
- `supervisor`
- `none`

约束：

- `spec_standard` 表示当前 execution record 采用的规范体系
- `spec_ref` 用于指向规范文档、spec 目录或 workflow 入口
- 这两个字段属于 Vibe 扩展层，不改变 GitHub 官方对象身份

## 5. Subtask Shape

`subtasks` 为对象数组，每个元素固定包含：

```json
{
  "subtask_id": "rewrite-frontmatter",
  "title": "Rewrite frontmatter",
  "status": "completed",
  "created_at": "2026-03-08T10:00:00+08:00",
  "updated_at": "2026-03-08T10:05:00+08:00",
  "completed_at": "2026-03-08T10:05:00+08:00"
}
```

`subtask.status` 与 task 使用同一组执行态状态枚举。

## 6. Runtime Rules

- `runtime_worktree_name`
- `runtime_worktree_path`
- `runtime_branch`
- `runtime_agent`

以上字段只表示当前 runtime 绑定。

约束：

- task 完成后必须清空 runtime 字段
- task 归档后必须清空 runtime 字段
- `runtime_*` 字段不能当作历史索引

## 7. Relationship Rules

- `roadmap_item_ids` 用于关联 roadmap item
- `issue_refs` 用于关联 repo issue
- `pr_ref` 只允许单值
- `related_task_ids` 用于 task 之间的松耦合关联

补充约束：

- `task` 是 execution record，不是 GitHub `type=task` item 的本地副本
- 若 roadmap item 的 `type=task` 需要执行，可以关联一个或多个本地 `task`
- `roadmap_item_ids` 只表达“此 execution record 服务哪些 roadmap items”，不改变 roadmap item 类型
- `issue_refs` 只桥接需求来源，不把 `repo issue` 变成 execution record 身份
- `pr_ref` 只桥接当前主交付单元，不记录 PR 历史列表
- `spec_standard` / `spec_ref` 只表达执行规范选择，不承担 roadmap 规划分类
- 一个 task 只允许一个主 PR
- 一个 task 不允许多个 PR 历史数组
- task 作为 execution record，不承担 roadmap item `type` 的定义职责

## 8. Prohibited Fields

禁止在 task 对象中写入：

- `priority`
- `version_goal`
- `dirty`
- `worktree_history`
- `pr_history`
- `feature`
- `repo`
- `milestone`
- `roadmap_type`
- `content_type`
- `github_project_item_id`

## 9. Minimal Example

```json
{
  "schema_version": "v2",
  "tasks": [
    {
      "task_id": "2026-03-08-command-standard-rewrite",
      "title": "Rewrite command standard",
      "description": null,
      "status": "todo",
      "source_type": "local",
      "source_refs": [],
      "roadmap_item_ids": [],
      "issue_refs": [],
      "pr_ref": null,
      "related_task_ids": [],
      "current_subtask_id": null,
      "subtasks": [],
      "runtime_worktree_name": null,
      "runtime_worktree_path": null,
      "runtime_branch": null,
      "runtime_agent": null,
      "next_step": null,
      "created_at": "2026-03-08T10:00:00+08:00",
      "updated_at": "2026-03-08T10:00:00+08:00",
      "completed_at": null,
      "archived_at": null
    }
  ]
}
```
