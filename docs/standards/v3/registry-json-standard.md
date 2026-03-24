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
last_updated: 2026-03-24
related_docs:
  - SOUL.md
  - CLAUDE.md
  - docs/standards/glossary.md
  - docs/standards/v3/data-model-standard.md
  - docs/standards/v3/command-standard.md
---

# `registry.json` Standard (V3 Migration Guide)

**⚠️ IMPORTANT**: In Vibe Center 3.0 (v3), the `registry.json` file has been **deprecated** and replaced with a SQLite database table `flow_issue_links`.

This document serves as a migration guide and reference for understanding the legacy `registry.json` structure and how it maps to the new v3 database schema.

本文档记录 v2 遗留 `registry.json` 的结构与迁移映射，供理解历史数据和迁移逻辑使用。v3 当前执行态真源以 [data-model-standard.md](data-model-standard.md) 定义的 SQLite 表与 GitHub 外部对象为准。

本文档涉及的 `task`、`repo issue`、`roadmap item`、`worktree`、`branch`、`pr` 等正式术语以 [glossary.md](../glossary.md) 为准。

## 1. V3 Architecture Change

### V2 (Legacy): JSON File
```
.git/vibe/
  └── registry.json          # Task execution records
  └── roadmap.json           # Roadmap items
  └── worktrees.json         # Worktree states
```

### V3 (Current): SQLite Database
```
.git/vibe/
  └── vibedb.sqlite3         # Unified SQLite database
     └── flow_issue_links   # Task-issue mapping table
     └── flow_states        # Flow runtime states
     └── roadmap_items      # Roadmap persistence
     └── worktrees          # Worktree metadata
```

## 2. File Responsibility (Legacy - V2)

`registry.json` 只负责：

- task 主记录（execution record）
- task 生命周期状态
- task 与 roadmap / repo issue / PR 的关联
- task 的主闭环 issue 落点
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

## 3. V3 Database Schema

### `flow_issue_links` Table (Replaces registry.json)

```sql
CREATE TABLE flow_issue_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flow_id TEXT NOT NULL,                    -- Unique flow identifier (was task_id)
    repo TEXT NOT NULL,                       -- Repository identifier
    issue_number INTEGER,                     -- Linked GitHub issue
    issue_url TEXT,                           -- Full issue URL
    link_type TEXT DEFAULT 'tracks',          -- Relationship type
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(flow_id, repo, issue_number)
);
```

### Migration from registry.json

| registry.json Field | V3 Database Location |
|--------------------|---------------------|
| `task_id` | `flow_issue_links.flow_id` |
| `status` | `flow_states.status` (new table) |
| `roadmap_item_ids` | `roadmap_items` table |
| `issue_refs` | `flow_issue_links` table |
| `primary_issue_ref` | `flow_issue_links` with `link_type='primary'` |
| `pr_ref` | `flow_states.pr_url` |
| `runtime_worktree_name` | `worktrees.name` |
| `runtime_worktree_path` | `worktrees.path` |
| `runtime_branch` | `flow_states.branch` |
| `runtime_agent` | `flow_states.agent` |
| `created_at` | `flow_issue_links.created_at` |
| `updated_at` | `flow_issue_links.updated_at` |

## 4. Root Shape (Legacy - V2)

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

## 5. Task Shape (Legacy - V2)

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
  "primary_issue_ref": null,
  "pr_ref": null,
  "related_task_ids": [],
  "current_subtask_id": null,
  "subtasks": [],
  "runtime_worktree_name": "wt-claude-refactor",
  "runtime_worktree_path": "/path/to/wt-claude-refactor",
  "runtime_branch": "claude/refactor",
  "runtime_agent": "claude",
  "next_step": "Rewrite docs/standards/v3/command-standard.md",
  "created_at": "2026-03-08T10:00:00+08:00",
  "updated_at": "2026-03-08T10:30:00+08:00",
  "completed_at": null,
  "archived_at": null
}
```

## 6. Field Rules (Legacy - V2)

### 6.1 Required Fields

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
- `primary_issue_ref`
- `related_task_ids`
- `subtasks`
- `created_at`
- `updated_at`

### 6.2 Optional or Nullable Fields

以下字段允许为 `null`：

- `description`
- `spec_ref`
- `primary_issue_ref`
- `pr_ref`
- `current_subtask_id`
- `runtime_worktree_name`
- `runtime_worktree_path`
- `runtime_branch`
- `runtime_agent`
- `next_step`
- `completed_at`
- `archived_at`

### 6.3 Status Enum

`status` 只允许：

- `todo`
- `in_progress`
- `blocked`
- `completed`
- `archived`

### 6.4 Source Enum

`source_type` 只允许：

- `issue`
- `local`
- `openspec`

`source_type` 表示 execution record 的创建来源，不表示 GitHub Project item 类型：

- `issue` = 由 `repo issue` 驱动创建
- `local` = 由本地执行决策创建
- `openspec` = 由 OpenSpec 执行输入创建

### 6.5 Spec Standard Enum

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

## 7. Subtask Shape (Legacy - V2)

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

## 8. Runtime Rules (Legacy - V2)

- `runtime_worktree_name`
- `runtime_worktree_path`
- `runtime_branch`
- `runtime_agent`

以上字段只表示当前 runtime 绑定。

约束：

- task 完成后必须清空 runtime 字段
- task 归档后必须清空 runtime 字段
- `runtime_*` 字段不能当作历史索引

## 9. Relationship Rules (Legacy - V2)

- `roadmap_item_ids` 用于关联 roadmap item
- `issue_refs` 用于关联 repo issue
- `primary_issue_ref` 用于指定当前 task 的主闭环 issue
- `pr_ref` 只允许单值
- `related_task_ids` 用于 task 之间的松耦合关联

补充约束：

- `task` 是 execution record，不是 GitHub `type=task` item 的本地副本
- 若 roadmap item 的 `type=task` 需要执行，可以关联一个或多个本地 `task`
- `roadmap_item_ids` 只表达"此 execution record 服务哪些 roadmap items"，不改变 roadmap item 类型
- `issue_refs` 只桥接需求来源，不把 `repo issue` 变成 execution record 身份
- `primary_issue_ref` 若存在，必须同时出现在 `issue_refs` 中；它表达的是 `task issue` 角色，而不是新的对象类型
- `pr_ref` 只桥接当前主交付单元，不记录 PR 历史列表
- `spec_standard` / `spec_ref` 只表达执行规范选择，不承担 roadmap 规划分类
- 一个 task 只允许一个主 PR
- 一个 task 不允许多个 PR 历史数组
- task 作为 execution record，不承担 roadmap item `type` 的定义职责

## 10. Prohibited Fields (Legacy - V2)

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

## 11. Migration to V3 (SQLite Database)

### New Database-Centric Model

In Vibe Center 3.0 (v3), the data persistence layer has been completely re-architected:

| Aspect | V2 (Legacy) | V3 (Current) |
|--------|-------------|--------------|
| **Storage** | JSON files in `.git/vibe/` | SQLite database `.git/vibe/vibedb.sqlite3` |
| **Task Records** | `registry.json` | `flow_issue_links` + `flow_states` tables |
| **Roadmap** | `roadmap.json` | `roadmap_items` table |
| **Worktrees** | `worktrees.json` | `worktrees` table |
| **Querying** | In-memory JSON manipulation | SQL queries via Pydantic models |
| **Concurrency** | File locking | ACID transactions |

### Python Model Mapping

```python
# V3 uses Pydantic models with SQLite backing

from vibe3.models import Flow, FlowState, IssueRef

# Creating a flow (replaces registry.json task record)
flow = Flow(
    flow_id="2026-03-08-command-standard-rewrite",
    repo="owner/repo",
    title="Rewrite command standard",
    description="Replace obsolete command spec with shared-state command standard.",
    status="in_progress",
    source_type="local",
    spec_standard="openspec",
    roadmap_item_ids=["roadmap-command-standard"],
)

# Persisting to database
flow.save()  # Stored in flow_states table

# Linking issues (replaces issue_refs in registry.json)
issue_link = IssueRef(
    flow_id=flow.flow_id,
    repo=flow.repo,
    issue_number=123,
    issue_url="https://github.com/owner/repo/issues/123",
    link_type="tracks",  # or "closes", "relates_to"
    is_primary=True,     # Replaces primary_issue_ref
)
issue_link.save()  # Stored in flow_issue_links table
```

### Schema Mapping: registry.json → SQLite Tables

| registry.json Path | SQLite Table.Column | Notes |
|--------------------|---------------------|-------|
| `tasks[].task_id` | `flow_states.flow_id` | Primary key for flows |
| `tasks[].title` | `flow_states.title` | Flow title |
| `tasks[].description` | `flow_states.description` | Flow description |
| `tasks[].status` | `flow_states.status` | Enum: todo, in_progress, blocked, completed, archived |
| `tasks[].source_type` | `flow_states.source_type` | Enum: issue, local, openspec |
| `tasks[].source_refs` | `flow_states.source_refs` | JSON array of source references |
| `tasks[].spec_standard` | `flow_states.spec_standard` | Enum: openspec, kiro, superpowers, supervisor, none |
| `tasks[].spec_ref` | `flow_states.spec_ref` | Reference to spec document |
| `tasks[].roadmap_item_ids` | `roadmap_items` table | Join via roadmap_links table |
| `tasks[].issue_refs` | `flow_issue_links` | Separate table for issue relationships |
| `tasks[].primary_issue_ref` | `flow_issue_links.is_primary` | Boolean flag on issue link |
| `tasks[].pr_ref` | `flow_states.pr_url` | Single PR URL |
| `tasks[].related_task_ids` | `flow_relationships` table | Related flows table |
| `tasks[].subtasks` | `subtasks` table | Separate table for subtasks |
| `tasks[].runtime_worktree_name` | `worktrees.name` | Join via flow_states.worktree_id |
| `tasks[].runtime_worktree_path` | `worktrees.path` | Worktree path |
| `tasks[].runtime_branch` | `flow_states.branch` | Git branch |
| `tasks[].runtime_agent` | `flow_states.agent` | AI agent identifier |
| `tasks[].next_step` | `flow_states.next_step` | Next action description |
| `tasks[].created_at` | `flow_states.created_at` | Creation timestamp |
| `tasks[].updated_at` | `flow_states.updated_at` | Last update timestamp |
| `tasks[].completed_at` | `flow_states.completed_at` | Completion timestamp |
| `tasks[].archived_at` | `flow_states.archived_at` | Archive timestamp |

## 5. Access Patterns (V3 Python)

```python
# Querying flows (replaces registry.json access)
from vibe3.models import Flow

# Get all active flows
active_flows = Flow.find_all(status="in_progress")

# Get flow by ID
flow = Flow.find_by_id("2026-03-08-command-standard-rewrite")

# Get flows linked to a roadmap item
roadmap_flows = Flow.find_by_roadmap_item("roadmap-command-standard")

# Get flows linked to an issue
issue_flows = Flow.find_by_issue(repo="owner/repo", issue_number=123)
```

## 6. Validation Rules (V3)

V3 uses Pydantic models for validation instead of JSON Schema:

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from enum import Enum

class FlowStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    ARCHIVED = "archived"

class SourceType(str, Enum):
    ISSUE = "issue"
    LOCAL = "local"
    OPENSPEC = "openspec"

class SpecStandard(str, Enum):
    OPENSPEC = "openspec"
    KIRO = "kiro"
    SUPERPOWERS = "superpowers"
    SUPERVISOR = "supervisor"
    NONE = "none"

class Flow(BaseModel):
    """V3 Flow model (replaces registry.json task)"""
    flow_id: str = Field(..., description="Unique flow identifier")
    repo: str = Field(..., description="Repository identifier")
    title: str = Field(..., min_length=1)
    description: Optional[str] = None
    status: FlowStatus = Field(default=FlowStatus.TODO)
    source_type: SourceType = Field(default=SourceType.LOCAL)
    source_refs: List[str] = Field(default_factory=list)
    spec_standard: SpecStandard = Field(default=SpecStandard.NONE)
    spec_ref: Optional[str] = None
    roadmap_item_ids: List[str] = Field(default_factory=list)
    pr_url: Optional[str] = None
    branch: Optional[str] = None
    agent: Optional[str] = None
    next_step: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None
```

## 7. Migration Checklist

When migrating from v2 to v3:

1. **Data Migration**
   - [ ] Export `registry.json` tasks to SQLite `flow_states` table
   - [ ] Export `roadmap.json` items to `roadmap_items` table
   - [ ] Export `worktrees.json` to `worktrees` table
   - [ ] Migrate `issue_refs` to `flow_issue_links` table

2. **Code Migration**
   - [ ] Replace JSON file I/O with SQL queries
   - [ ] Replace `Task` class with `Flow` Pydantic model
   - [ ] Update validation from JSON Schema to Pydantic
   - [ ] Update CLI commands to use new database API

3. **Documentation Update**
   - [ ] Update standards references from v2 to v3
   - [ ] Document new database schema
   - [ ] Provide migration examples

## 8. Related Documentation

- **V3 Data Model**: `docs/standards/v3/data-model-standard.md`
- **V3 Command Standard**: `docs/standards/v3/command-standard.md`
- **V2 Legacy Standard**: `docs/standards/v3/registry-json-standard.md` (this document's predecessor)

---

**Document Status**: This is a migration guide documenting the transition from V2 JSON files to V3 SQLite database. For current V3 implementation details, refer to the `flow_issue_links` table schema and `vibe3.models.Flow` Pydantic model.
