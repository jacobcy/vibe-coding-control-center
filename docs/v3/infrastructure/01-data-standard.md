---
document_type: implementation-guide
title: Data Standard - Architecture Clarification
status: active
author: Claude Sonnet 4.6
created: 2026-03-16
last_updated: 2026-03-16
related_docs:
  - docs/standards/v3/handoff-store-standard.md
  - docs/standards/v3/github-remote-call-standard.md
  - docs/standards/glossary.md
  - docs/v3/handoff/02-flow-task-foundation.md
---

# 数据标准 - 架构澄清

> **目的**: 澄清 Vibe 3.0 的数据架构原则，统一数据库字段要求。
> **真源**: 数据库字段定义以 [handoff-store-standard.md](../../standards/v3/handoff-store-standard.md) 为准。
> **GitHub 调用**: 远端调用以 [github-remote-call-standard.md](../../standards/v3/github-remote-call-standard.md) 为准。

---

## 核心原则（强制）

### 真源层级

```
GitHub 层（唯一真源 - gh CLI 直接访问）
├── GitHub Project Items (task, feature, bug) - 规划层真源
├── GitHub Issues - 来源层真源
├── GitHub PRs (pr) - 交付层真源
└── Git Branches (flow 身份锚点)

本地层（执行记录 - 责任链索引）
├── SQLite Handoff Store (.git/vibe3/handoff.db) - 执行过程记录
│   ├── handoff 记录（plan/execute/review 三阶段）
│   ├── 规范文件引用（spec ref）
│   ├── agent 署名（谁做了什么）
│   └── 追责记录（问题、决策、解决方案）
├── .agent/context/task.md - v2 兼容 handoff
└── PR metadata (注入到 PR description) - 过程记录
```

### gh CLI 是唯一真源

**包装原则**:
- ✅ git 命令能做的 → 只包装，不缓存
- ✅ gh CLI 能做的 → 只包装，不缓存
- ✅ PR 数据 → 从 gh 实时读取
- ✅ Task 状态 → 从 gh project item 实时读取
- ❌ 任何业务数据 → 不做本地缓存

**追责与审计**:
- 本地 handoff store 的核心价值是**追责**和**审计**
- 每条记录必须包含：agent、model、timestamp、操作内容
- 发生问题时，可以追溯到具体 agent、具体决策、具体规范引用

---

## 数据库字段标准

### 真源引用

**数据库字段定义**: 见 [docs/standards/v3/handoff-store-standard.md](../../standards/v3/handoff-store-standard.md) §4 "Core Tables"

**不允许重复定义字段**，所有实现必须严格遵循标准文档。

### 关键字段说明

#### `session_id` 字段（预留）

```sql
planner_session_id TEXT,
executor_session_id TEXT,
reviewer_session_id TEXT,
```

**用途**:
- 用于记录和恢复 agent 会话的字段
- **现阶段仅保留字段，不实现功能**
- 面向未来设计，用于会话连续性支持

**实现约束**:
- 建表时必须包含这些字段
- 当前版本允许为 NULL
- 不写入任何值，不验证格式

#### `*_actor` 字段

```sql
planner_actor TEXT,
executor_actor TEXT,
reviewer_actor TEXT,
latest_actor TEXT,
```

**格式要求**:
- 必须使用 `agent/model` 形态
- 示例：`codex/gpt-5.4`、`claude/sonnet-4.5`

#### `*_ref` 字段

```sql
spec_ref TEXT,
plan_ref TEXT,
report_ref TEXT,
audit_ref TEXT,
```

**格式要求**:
- 存储文档路径，不复制正文
- 示例：`docs/plans/example.md`

---

## SQLite 表结构引用

### 必需的表

所有表定义见真源文档，**不允许在本文档或其他文档中重复定义**：

1. **`flow_state` 表**
   - 真源: [handoff-store-standard.md](../../standards/v3/handoff-store-standard.md) §4.1
   - 职责: 记录 flow 责任链主记录

2. **`flow_issue_links` 表**
   - 真源: [handoff-store-standard.md](../../standards/v3/handoff-store-standard.md) §4.2
   - 职责: 记录 flow 与 issue 的多对多关系

3. **`flow_events` 表**
   - 真源: [handoff-store-standard.md](../../standards/v3/handoff-store-standard.md) §4.3
   - 职责: 审计辅助表，记录最小事件

4. **`schema_meta` 表**
   - 真源: [handoff-store-standard.md](../../standards/v3/handoff-store-standard.md) §3
   - 职责: schema 版本管理

---

## 错误示例对比

### ❌ 错误：缓存 GitHub 数据

```python
# 错误：缓存 PR 数据到 SQLite
def pr_show_wrong(pr_number: int) -> None:
    pr_data = store.get_cached_pr(pr_number)  # 不要缓存 PR！
    render_pr(pr_data)
```

### ✅ 正确：实时读取

```python
# 正确：PR 只作为指针，实时读取
def pr_show(pr_number: int) -> None:
    pr_data = github_client.get_pr(pr_number)  # 实时读取
    handoff = store.get_flow_handoff(branch)    # 读取 handoff 索引
    render_pr_with_handoff(pr_data, handoff)
```

### ❌ 错误：重复定义字段

```markdown
<!-- 错误：在多个文档中重复定义 -->
CREATE TABLE flow_state (
  branch TEXT PRIMARY KEY,
  task_issue_number INTEGER,
  ...
);
```

### ✅ 正确：引用真源

```markdown
<!-- 正确：引用标准文档 -->
数据库字段定义见 [handoff-store-standard.md](../../standards/v3/handoff-store-standard.md) §4.1
```

---

## 文档冲突修正历史

### 已修正的文档

以下文档已修正，删除了重复定义，改为引用真源：

1. **`docs/v3/handoff/02-flow-task-foundation.md`**
   - 修正前: 声称 SQLite 是"唯一真源"
   - 修正后: 明确为"责任链索引"

2. **`docs/v3/handoff/v3-rewrite-plan.md`**
   - 修正前: "Implement CRUD logic for Flows and Tasks"
   - 修正后: "Implement handoff store for Flow's three-phase process"

3. **`docs/v3/handoff/03-pr-domain.md`**
   - 修正前: 未说明 SQLite 存储什么
   - 修正后: 明确只存储 handoff 记录

4. **`docs/v3/execution_plan/implementation-spec-phase3-draft.md`**
   - 修正前: "更新 SQLite task 状态"
   - 修正后: "更新 GitHub Project task 状态，SQLite 只记录 handoff"

5. **`docs/v3/handoff/README.md`**
   - 修正前: "核对 handoff store 与远端真源"
   - 修正后: 补充"远端真源 = GitHub Project/Issues/PRs（通过 gh CLI 访问）"

---

## 实现检查清单

在实现 Phase 3 之前，逐项确认：

- [ ] 所有文档中的"唯一真源"已修正或删除
- [ ] 所有提到"缓存 PR/Task 数据"的地方已删除或标注为错误示例
- [ ] 实现代码中没有创建 `pr_cache` 或 `task_cache` 表
- [ ] Client 层只包装 gh 命令，不做本地缓存
- [ ] Service 层调用 Client 实时读取，不依赖本地缓存
- [ ] `session_id` 字段在建表时包含，但不实现功能
- [ ] 所有 `*_actor` 字段使用 `agent/model` 格式

---

## 参考文档（真源）

### 标准文档

- **[docs/standards/v3/handoff-store-standard.md](../../standards/v3/handoff-store-standard.md)** - 数据库字段真源 ⭐
- **[docs/standards/v3/github-remote-call-standard.md](../../standards/v3/github-remote-call-standard.md)** - GitHub 调用标准 ⭐
- **[docs/standards/glossary.md](../../standards/glossary.md)** - 术语真源

### 实施文档

- **[docs/v3/handoff/02-flow-task-foundation.md](../plans/02-flow-task-foundation.md)** - Phase 2 计划
- **[docs/v3/infrastructure/02-architecture.md](02-architecture.md)** - 架构设计

---

**维护者**: Vibe Team
**最后更新**: 2026-03-16