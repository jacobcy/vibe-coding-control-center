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
- GitHub Project item 的稳定桥接字段
- 允许双向同步的 Vibe 扩展字段

`roadmap.json` 不负责：

- task execution record 本体
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
  "github_project_item_id": null,
  "content_type": "draft_issue",
  "spec_standard": null,
  "execution_record_id": null,
  "spec_ref": null,
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
- `github_project_item_id`
- `content_type`
- `spec_standard`
- `execution_record_id`
- `spec_ref`
- `issue_refs`
- `linked_task_ids`
- `created_at`
- `updated_at`

### 4.2 Optional or Nullable Fields

以下字段允许为 `null`：

- `version_goal`
- `description`
- `milestone`
- `github_project_item_id`
- `spec_standard`
- `execution_record_id`
- `spec_ref`

说明：

- 根字段 `milestone` 保留，作为当前规划窗口的标准锚点
- 根字段 `version_goal` 保留，但只作为兼容性文本锚点，不替代 milestone
- item 级 `source_refs` 用于记录 GitHub Project item / issue 等来源引用

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

### 4.6 GitHub Alignment Fields

`content_type` 只允许：

- `issue`
- `pull_request`
- `draft_issue`

约束：

- `content_type` 表达 GitHub Project item 的官方来源类型
- `github_project_item_id` 用于稳定对齐 GitHub Project item 身份
- 这两个字段属于 GitHub 官方层，不得被本地 workflow 语义覆盖

### 4.7 Vibe Extension Fields

`spec_standard` 只允许：

- `openspec`
- `kiro`
- `superpowers`
- `supervisor`
- `none`

约束：

- `spec_standard` 是 Vibe 扩展字段，不是 GitHub 官方字段
- `execution_record_id` 用于桥接本地 `registry.json.task_id`
- `spec_ref` 用于指向规范文档或执行规范入口
- 扩展字段必须可双向同步，但不得改变 GitHub item 的官方身份字段

## 5. Relationship Rules

- `linked_task_ids` 用于关联执行层 task
- `issue_refs` 用于关联 repo issue
- `source_refs` 用于记录导入来源

补充约束：

- `roadmap item` 是 mirrored `GitHub Project item`，不是任意本地 feature 草稿
- `type=feature|task|bug` 只表达规划分类，足以覆盖当前标准层需求
- 若未来需要更高层规划对象，应新增独立标准，而不是让 roadmap item 混装 `epic`
- `source_refs` 应优先记录 GitHub Project item / repo issue 来源，而不是本地运行时来源
- `github_project_item_id` + `content_type` 是 GitHub Project 对齐主桥
- `spec_standard` / `execution_record_id` / `spec_ref` 是 Vibe 扩展桥
- 一个 roadmap item 可以关联多个 task
- 一个 roadmap item 可以关联多个 repo issue
- 一个 `type=feature` 的 roadmap item 可以拆分出多个 `type=task` item 或多个 execution record
- 一个 `type=task` 的 roadmap item 也可以继续拆成多个 execution record
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
- `runtime_worktree_name`
- `runtime_branch`
- `runtime_agent`

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
      "github_project_item_id": null,
      "content_type": "draft_issue",
      "spec_standard": "none",
      "execution_record_id": null,
      "spec_ref": null,
      "issue_refs": [],
      "linked_task_ids": [],
      "created_at": "2026-03-08T09:00:00+08:00",
      "updated_at": "2026-03-08T09:00:00+08:00"
    }
  ]
}
```
