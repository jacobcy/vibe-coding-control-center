---
document_type: standard
title: Roadmap JSON Standard
status: approved
scope: shared-state
authority:
  - roadmap-json-schema
  - roadmap-item-fields
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

# `roadmap.json` 标准

本文档定义 `roadmap.json` 的最终文件结构。它是规划态共享真源，只表达 mirrored `GitHub Project item`、规划窗口和兼容性的版本目标，不表达执行层或现场层事实。

本文档涉及的 `roadmap item`、`task`、`repo issue`、`worktree`、`branch`、`pr` 等正式术语以 [glossary.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/glossary.md) 为准。

## 1. File Responsibility

`roadmap.json` 只负责：

- roadmap item（mirrored GitHub Project item）
- roadmap item 状态
- milestone / 兼容性的 `version_goal`
- roadmap item 与 task / repo issue 的映射

`roadmap.json` 不负责：

- branch
- worktree
- `dirty`
- task runtime
- PR 历史
- 当前版本号真源

## 2. Root Shape

根对象固定为：

```json
{
  "schema_version": "v2",
  "milestone": null,
  "version_goal": null,
  "items": []
}
```

根对象只允许：

- `schema_version`
- `milestone`
- `version_goal`
- `items`

## 3. Roadmap Item Shape

每个 roadmap item 对象固定包含以下字段：

```json
{
  "roadmap_item_id": "roadmap-command-standard",
  "title": "Standardize shared-state command model",
  "description": "Define final command semantics for roadmap, task, flow, and check.",
  "type": "feature",
  "status": "current",
  "source_type": "local",
  "source_refs": [],
  "issue_refs": [],
  "linked_task_ids": [
    "2026-03-08-command-standard-rewrite"
  ],
  "created_at": "2026-03-08T09:00:00+08:00",
  "updated_at": "2026-03-08T10:00:00+08:00"
}
```

## 4. Field Rules

### 4.1 Required Fields

以下字段必须存在：

- `roadmap_item_id`
- `title`
- `type`
- `status`
- `source_type`
- `source_refs`
- `issue_refs`
- `linked_task_ids`
- `created_at`
- `updated_at`

### 4.2 Optional or Nullable Fields

以下字段允许为 `null`：

- `version_goal`
- `description`
- `milestone`

### 4.3 Status Enum

`status` 只允许：

- `p0`
- `current`
- `next`
- `deferred`
- `rejected`

### 4.4 Source Enum

`source_type` 只允许：

- `github`
- `local`

### 4.5 Type Enum

`type` 只允许：

- `feature`
- `task`
- `bug`

## 5. Relationship Rules

- `linked_task_ids` 用于关联执行层 task
- `issue_refs` 用于关联 repo issue
- `source_refs` 用于记录导入来源

补充约束：

- 一个 roadmap item 可以关联多个 task
- 一个 roadmap item 可以关联多个 repo issue
- 一个 `type=feature` 的 roadmap item 可以拆分出多个 `type=task` item 或多个 execution record
- roadmap item 不直接持有 PR 字段

## 6. Version Goal Rules

- `milestone` 是根对象字段，表示当前版本或阶段窗口
- `version_goal` 是根对象字段
- `version_goal` 表示当前规划窗口目标的兼容性文本锚点
- `version_goal` 不是当前版本号

禁止：

- `current_version`
- `next_version`
- `version_bump`

## 7. Prohibited Fields

禁止在 `roadmap.json` 中写入：

- `branch`
- `worktree`
- `dirty`
- `pr_ref`
- `pr_history`
- `feature`
- `epic`
- `current_version`

## 8. Minimal Example

```json
{
  "schema_version": "v2",
  "milestone": "v2.1",
  "version_goal": "Complete shared-state standardization",
  "items": [
    {
      "roadmap_item_id": "roadmap-command-standard",
      "title": "Standardize shared-state command model",
      "description": null,
      "type": "feature",
      "status": "current",
      "source_type": "local",
      "source_refs": [],
      "issue_refs": [],
      "linked_task_ids": [],
      "created_at": "2026-03-08T09:00:00+08:00",
      "updated_at": "2026-03-08T09:00:00+08:00"
    }
  ]
}
```
