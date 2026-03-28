---
document_type: standard
title: Vibe3 Handoff Store Standard
status: proposed
scope: vibe3-handoff-store
authority:
  - vibe3-local-store
  - vibe3-field-schema
  - vibe3-read-write-rules
author: GPT-5 Codex
created: 2026-03-14
last_updated: 2026-03-23
related_docs:
  - docs/prds/vibe-session-governance.md
  - docs/standards/v3/handoff-governance-standard.md
  - docs/plans/2026-03-14-vibe3-data-model-design.md
---

# Vibe3 Handoff Store Standard

本文档定义 Vibe 3.0 handoff system 的正式本地结构。

它只负责记录：

- flow 责任链
- `plan / report / audit` ref
- `planner / executor / reviewer` 署名
- 最小阻塞与下一步信息
- 共享 handoff 中间态文件的位置约定

它不负责：

- GitHub Project 镜像
- issue 正文缓存
- PR 全量状态缓存
- task registry
- roadmap mirror

## 1. Storage Choice

Vibe 3.0 handoff system 固定采用两层：

- **SQLite**: 最小责任链与索引
- **Shared Markdown Buffer**: 结构化 handoff 中间态

原因：

- SQLite 单文件，适合本地最小状态与唯一键约束
- Markdown 更适合 agent 直接编辑 handoff 内容
- 两层组合可以传递上下文，又不会自然膨胀成第二真源
- 便于 `vibe check` 做一致性校验

当前不采用：

- JSON / YAML 作为主 handoff 文件
- item 级 CRUD + 双向同步系统
- 进程级 `sessions.json`

## 2. File Location

SQLite store 文件位置固定为：

```text
.git/vibe3/handoff.db
```

共享 handoff 中间态文件位置固定为：

```text
.git/vibe3/handoff/<branch-safe>/current.md
```

补充约束：

- 不提交到 Git
- 不放到仓库根目录
- 不放到 `docs/`
- 不放到 `.agent/context/`
- 不把 `.agent/context/task.md` 当作共享 handoff 正文载体

## 3. Schema Version

数据库必须包含 schema 版本表：

```sql
CREATE TABLE schema_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
```

初始化后至少写入：

| key | value |
|---|---|
| `schema_version` | `v3` |
| `store_type` | `handoff_store` |

## 4. Core Tables

### 4.1 `flow_state`

这是主表，每个 branch 对应一条当前责任链记录。

```sql
CREATE TABLE flow_state (
  branch TEXT PRIMARY KEY,
  flow_slug TEXT NOT NULL,
  task_issue_number INTEGER,
  pr_number INTEGER,
  spec_ref TEXT,
  plan_ref TEXT,
  report_ref TEXT,
  audit_ref TEXT,
  planner_actor TEXT,
  planner_session_id TEXT,
  executor_actor TEXT,
  executor_session_id TEXT,
  reviewer_actor TEXT,
  reviewer_session_id TEXT,
  latest_actor TEXT,
  blocked_by TEXT,
  next_step TEXT,
  flow_status TEXT NOT NULL DEFAULT 'active',
  updated_at TEXT NOT NULL
);
```

字段约束：

- `branch`
  - 本地 runtime 主键
- `flow_slug`
  - 用户可读 flow 名称
- `task_issue_number`
  - 单值，允许为空
- `pr_number`
  - 单值，允许为空
- `spec_ref`
  - 文档引用，不复制正文
- `plan_ref` / `report_ref` / `audit_ref`
  - 文档引用，不复制正文
- `planner_actor` / `executor_actor` / `reviewer_actor`
  - 必须使用 `agent/model` 形态
  - 示例：`codex/gpt-5.4`
- `planner_session_id` / `executor_session_id` / `reviewer_session_id`
  - 用于记录和恢复会话的字段
  - 现阶段仅保留字段，不实现功能
  - 面向未来设计，用于会话连续性支持
- `latest_actor`
  - 最近一次写入 handoff 的 actor
- `blocked_by`
  - 文本提示字段，可存 `#123`、`task/xxx`、`pr#17`
- `next_step`
  - 简短下一步提示
- `flow_status`
  - 只允许：`active`, `blocked`, `done`, `stale`
- `updated_at`
  - ISO 8601 时间戳

### 4.2 `flow_issue_links`

这张表只记录 flow 和 repo issue 的多对多关系。

```sql
CREATE TABLE flow_issue_links (
  branch TEXT NOT NULL,
  issue_number INTEGER NOT NULL,
  issue_role TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (branch, issue_number, issue_role)
);
```

字段约束：

- `issue_role` 只允许：
  - `task` - 主要任务 issue
  - `related` - 相关 issue
  - `dependency` - 依赖 issue

补充约束：

- 每个 branch 只能有一个 `issue_role='task'`
- 每个 branch 可以有多个 `issue_role='related'`
- 每个 branch 可以有多个 `issue_role='dependency'`

推荐额外建立唯一索引：

```sql
CREATE UNIQUE INDEX idx_flow_single_task_issue
ON flow_issue_links(branch)
WHERE issue_role = 'task';
```

### 4.3 `flow_events`

这是审计辅助表，只记录最小事件，不记录业务正文。

```sql
CREATE TABLE flow_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  branch TEXT NOT NULL,
  event_type TEXT NOT NULL,
  actor TEXT NOT NULL,
  detail TEXT,
  created_at TEXT NOT NULL
);
```

`event_type` 只允许：

**Flow 生命周期事件**：
- `flow_created` - flow 创建
- `flow_closed` - flow 关闭并删除分支
- `flow_blocked` - flow 标记为 blocked
- `flow_aborted` - flow 标记为 aborted

**Issue 相关事件**：
- `issue_linked` - issue 关联到 flow

**状态变更事件**：
- `status_updated` - flow 状态更新
- `next_step_set` - 设置 next step

**Handoff 事件**：
- `handoff_plan` - plan handoff
- `handoff_report` - report handoff
- `handoff_audit` - audit handoff

**PR 相关事件**：
- `pr_draft` - draft PR 创建
- `pr_ready` - PR 标记为 ready
- `pr_merge` - PR 合并

**检查与修复事件**：
- `check_fix` - check 修复

## 5. Shared Handoff Buffer

共享 `current.md` 是 handoff 的结构化中间态，不是主链真源。

### 5.1 Allowed Content

允许记录：

- findings
- blockers
- next actions
- open questions
- key files
- evidence refs
- `SESSION_ID`
- 当前阶段的简短总结

### 5.2 Forbidden Content

不允许记录：

- issue / PR / Project 正文镜像
- `plan / report / audit` 全文
- 可覆盖 SQLite 的正式责任链字段
- 与 GitHub / git 冲突的事实副本

### 5.3 Format

`current.md` 固定采用 Markdown 文件，并使用固定 section 模板。

第一版至少包含：

- `Meta`
- `Summary`
- `Findings`
- `Blockers`
- `Next Actions`
- `Key Files`
- `Evidence Refs`

允许轻量格式约定，但不要求 item 级严格 schema 校验。

## 6. Field Naming Standard

字段统一遵循：

- 本地字段使用 `snake_case`
- issue / PR 编号字段必须显式带类型后缀：
  - `task_issue_number`
  - `pr_number`
- ref 字段必须以 `_ref` 结尾：
  - `spec_ref`
  - `plan_ref`
  - `report_ref`
  - `audit_ref`
- actor 字段必须以 `_actor` 结尾

禁止：

- `task_id`
- `roadmap_item_id`
- `runtime_worktree_name`
- `runtime_branch`
- `pr_state`
- `issue_body`
- `project_item_json`

这些属于 V2 或镜像式心智，不属于 V3 handoff store。

## 7. Read Rules

`flow show` / `flow status` / `vibe check` 固定按这个顺序重建：

1. `git` 现场
2. GitHub `issue / PR / Project`
3. SQLite handoff store
4. 共享 `current.md`
5. `.agent/context/task.md` 本地草稿（可选）
6. `plan / report / audit` 文档存在性

解释约束：

- Git 与 GitHub 负责业务事实
- SQLite 只负责责任链补充
- 若 SQLite 与远端冲突，以远端为准

## 8. Write Rules

允许写入 SQLite 的命令只有：

**Flow 生命周期**：
- `flow new` - 创建新 flow 并创建分支
- `flow switch` - 切换到已存在的 flow
- `flow bind` - 绑定 issue 到 flow
- `flow done` - 关闭 flow 并删除分支
- `flow blocked` - 标记 flow 为 blocked
- `flow aborted` - 标记 flow 为 aborted 并删除分支

**Handoff 记录**：
- `handoff plan` - 记录 plan handoff
- `handoff report` - 记录 report handoff
- `handoff audit` - 记录 audit handoff
- `handoff append` - 追加轻量更新到 current.md

**PR 操作**：
- `pr draft` - 创建 draft PR
- `pr merge` - 合并 PR

**检查与修复**：
- `vibe check --fix` - 自动修复问题

写入原则：

- 只写责任链字段
- 不写 GitHub 对象正文
- 不写远端镜像 JSON
- 所有写入必须更新 `updated_at`
- 所有关键写入必须记录一条 `flow_events`

## 9. `vibe check` Contract

`vibe check` 在 V3 至少要做这些检查：

- 当前 branch 是否在 `flow_state` 中存在
- `flow_state.task_issue_number` 是否在远端仍存在
- `flow_issue_links` 中是否只有一个 `task`
- `flow_state.pr_number` 是否仍对应该 branch
- `plan_ref / report_ref / audit_ref` 文件是否存在
- `planner_actor / executor_actor / reviewer_actor` 是否与阶段交接物一致

输出分级：

- `ok`
- `warning`
- `hard_block`

`warning` 适用：

- 缺少 `report_ref`
- 缺少 `audit_ref`
- `next_step` 为空

`hard_block` 适用：

- `task_issue_number` 不存在
- `pr_number` 与 branch 不匹配
- 一个 branch 有多个 `task` role
- `plan_ref` 缺失

## 10. JSON Boundary

JSON 在 V3 只允许用于：

- CLI `--json` 输出
- 调试导出
- 测试 fixture

JSON 不允许作为 V3 正式持久化主存储。

## 11. Minimal Example

```sql
INSERT INTO flow_state (
  branch, flow_slug, task_issue_number, pr_number,
  spec_ref, plan_ref, report_ref, audit_ref,
  planner_actor, planner_session_id,
  executor_actor, executor_session_id,
  reviewer_actor, reviewer_session_id,
  latest_actor,
  blocked_by, next_step, flow_status, updated_at
) VALUES (
  'task/vibe3-parallel-rebuild',
  'vibe3-parallel-rebuild',
  157,
  169,
  'docs/plans/2026-03-13-vibe3-parallel-rebuild-design.md',
  'docs/tasks/2026-03-14-vibe3-data-model/plan-v1.md',
  NULL,
  NULL,
  'codex/gpt-5.4',
  NULL,
  NULL,
  NULL,
  NULL,
  NULL,
  'codex/gpt-5.4',
  NULL,
  'execute phase 2.1',
  'active',
  '2026-03-14T12:00:00+08:00'
);
```
