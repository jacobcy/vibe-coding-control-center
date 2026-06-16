---
document_type: standard
title: Database Schema Standard (v3)
status: active
scope: shared-state
authority:
  - database-schema
  - table-definitions
author: Vibe Team
created: 2026-05-25
last_updated: 2026-05-25
related_docs:
  - docs/standards/v3/data-model-standard.md
  - docs/standards/glossary.md
  - docs/standards/v3/event-driven-standard.md
---

# 数据库 Schema 标准 (v3)

本文档定义 Vibe Center v3 使用的 SQLite 数据库（`.git/vibe3/handoff.db`）的精确 Schema。

## 1. 核心表结构

### 1.1 `flow_state`

记录当前开放 flow 的运行时状态。

```sql
CREATE TABLE flow_state (
    branch TEXT PRIMARY KEY,                  -- Git 分支名，主索引
    flow_slug TEXT NOT NULL,                 -- Flow 显示名称
    spec_ref TEXT,                           -- 规范文档引用
    plan_ref TEXT,                           -- 执行计划引用
    report_ref TEXT,                         -- 执行报告引用
    audit_ref TEXT,                          -- 审计报告引用
    indicate_ref TEXT,                       -- Handoff 指示引用
    pr_ref TEXT,                             -- GitHub PR URL
    planner_actor TEXT,                      -- Planner 角色标识
    executor_actor TEXT,                     -- Executor 角色标识
    reviewer_actor TEXT,                     -- Reviewer 角色标识
    manager_actor TEXT,                      -- Manager 角色标识
    latest_actor TEXT,                       -- 最近一次操作的 Actor
    initiated_by TEXT,                       -- 流程发起方标识
    blocked_by_issue INTEGER,                -- 阻塞当前 Flow 的 Issue 编号
    blocked_reason TEXT,                     -- 阻塞原因描述
    next_step TEXT,                          -- 下一步建议动作
    flow_status TEXT NOT NULL DEFAULT 'active', -- 状态：active, blocked, done, stale, aborted
    updated_at TEXT NOT NULL,                -- ISO 8601 时间戳
    planner_status TEXT,                     -- Planner 执行状态 (pending, running, done, crashed, aborted)
    executor_status TEXT,                    -- Executor 执行状态
    reviewer_status TEXT,                    -- Reviewer 执行状态
    execution_pid INTEGER,                   -- 当前执行进程 PID
    execution_started_at TEXT,               -- 执行开始时间
    execution_completed_at TEXT,             -- 执行完成时间
    transition_count INTEGER DEFAULT 0       -- 状态流转计数（用于防死循环）
);
```

### 1.2 `flow_issue_links`

记录 Flow 与 GitHub Issue 的多对多关联关系。

```sql
CREATE TABLE flow_issue_links (
    branch TEXT NOT NULL,                    -- Flow 分支名
    issue_number INTEGER NOT NULL,           -- GitHub Issue 编号
    issue_role TEXT NOT NULL,                -- 角色：task, related, dependency
    created_at TEXT NOT NULL,                -- 创建时间
    PRIMARY KEY (branch, issue_number, issue_role)
);

-- 每个 Flow 只能有一个主要 Task Issue
CREATE UNIQUE INDEX idx_flow_single_task_issue 
ON flow_issue_links(branch) 
WHERE issue_role = 'task';
```

### 1.3 `flow_events`

记录 Flow 生命周期内的关键事件。

**重要**：此表存储 **FlowEvent** 记录（flow-local 审计投影），不是 **DomainEvent** 记录（运行时因果事件）。DomainEvent 到 FlowEvent 的投影规则见 [event-driven-standard.md](event-driven-standard.md) §十二。

```sql
CREATE TABLE flow_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    branch TEXT NOT NULL,                    -- 关联分支
    event_type TEXT NOT NULL,                -- 事件类型 (flow_created, state_transitioned 等)
    actor TEXT NOT NULL,                     -- 执行者
    detail TEXT,                             -- 事件详情文本
    refs TEXT,                               -- 关联元数据 (JSON)
    created_at TEXT NOT NULL                 -- 发生时间
);
```

### 1.4 `error_log`

记录运行时基础设施错误。

```sql
CREATE TABLE error_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tick_id INTEGER NOT NULL,                -- Heartbeat Tick ID
    error_code TEXT NOT NULL,                -- 错误代码
    error_message TEXT NOT NULL,             -- 错误消息
    severity TEXT,                           -- 严重程度 (CRITICAL, ERROR, WARNING)
    issue_number INTEGER,                    -- 关联 Issue (可选)
    branch TEXT,                             -- 关联分支 (可选)
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### 1.5 `FailedGate_state`

记录 FailedGate 的熔断状态。

```sql
CREATE TABLE FailedGate_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),   -- 单行记录约束
    is_active INTEGER NOT NULL DEFAULT 0,    -- 是否激活熔断
    reason TEXT,                             -- 激活原因
    triggered_at TEXT,                       -- 激活时间
    triggered_by_error_code TEXT,            -- 触发错误码
    cleared_at TEXT,                         -- 清除时间
    cleared_by TEXT,                         -- 清除者
    cleared_reason TEXT,                     -- 清除原因
    blocked_ticks INTEGER NOT NULL DEFAULT 0 -- 被阻塞的 Tick 计数
);
```

## 2. 辅助与缓存表

- `runtime_session`: 异步执行会话追踪
- `flow_context_cache`: 远端 GitHub 上下文的本地缓存
- `orchestra_queue`: Orchestra 待处理任务队列
- `transition_history`: 状态变迁历史

## 3. 约束与规则

1. **时间戳**: 统一使用 ISO 8601 字符串格式。
2. **JSON 存储**: `refs` 和 `latest_verdict` 等复杂结构使用 JSON 文本存储。
3. **并发控制**: 开启 WAL (Write-Ahead Logging) 模式以支持多进程并发读写。
4. **状态一致性**: `flow_status` 的变更必须伴随 `flow_events` 的记录。
