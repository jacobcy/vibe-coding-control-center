---
document_type: plan
title: Phase 02 - Flow & Task State (SQLite)
status: draft
author: Claude Sonnet 4.6
created: 2026-03-15
last_updated: 2026-03-16
related_docs:
  - docs/v3/plans/v3-rewrite-plan.md
  - docs/v3/implementation/02-architecture.md
  - docs/v3/implementation/03-coding-standards.md
  - docs/v3/implementation/04-test-standards.md
---

# Phase 02: Flow & Task State (SQLite)

**Goal**: Implement the state management layer for Flows and Tasks using SQLite.

## ⚠️ V3 架构约束（强制）

**必须遵守**：
- [02-architecture.md](../implementation/02-architecture.md) - 架构设计
- [03-coding-standards.md](../implementation/03-coding-standards.md) - 编码标准
- [04-test-standards.md](../implementation/04-test-standards.md) - 测试标准

### 数据存储方案（v3 vs v2）

**v3 使用 SQLite Handoff Store，不再使用 JSON 文件：**

| 对比项 | v2 | v3 |
|--------|----|----|
| 任务存储 | `registry.json` | ❌ 不使用 |
| Flow 存储 | `worktrees.json` + `registry.json` | ❌ 不使用 |
| 本地存储 | SQLite Handoff Store | 执行记录与追责索引 |
| 文件位置 | `.git/vibe3/handoff.db` | ✅ 按分支隔离 |

**核心原则**（来自 [README.md](README.md)）：
- **责任链落地**：本地只保留 flow-scoped handoff store（执行记录、规范、署名、追责）
- **真源回归**：gh CLI 是唯一真源，GitHub Issue / PR / Project 是业务真源
- SQLite 存储 handoff/署名/追责记录，**不存储 GitHub Project 镜像**

**实现规范：**
- ✅ 必须使用的技术栈（typer, rich, pydantic, loguru）
- ✅ 强制的目录结构
- ✅ 严格的分层职责
- ✅ 类型注解要求
- ✅ 测试要求（遵循 04-test-standards.md）
- ✅ 代码量限制（Services < 300 行，Commands < 100 行）
- ✅ 测试代码量限制（Services 测试 < 150 行，Commands 测试 < 80 行）

**违反规范将导致验收失败，不予合并。**

## 1. Context Anchor (Optional)

If you require more than technical scope, refer to the [Vibe 3.0 Master Plan](v3-rewrite-plan.md).

## 2. Pre-requisites (Executor Entry)

- [ ] Executor 01 has completed `bin/vibe3` skeleton.
- [ ] `scripts/python/vibe_core.py` is accessible.

## 3. 数据库 Schema（Handoff Store 真源）

v3 使用 SQLite 作为本地 handoff store，数据库位置：`.git/vibe3/handoff.db`

### 已实现的表结构（见 `scripts/python/lib/store.py`）

#### 3.1 `flow_state` 表
主表，记录 flow 的状态和元数据：
```sql
CREATE TABLE flow_state (
    branch TEXT PRIMARY KEY,           -- Git 分支名（flow 身份锚点）
    flow_slug TEXT NOT NULL,           -- Flow 名称
    task_issue_number INTEGER,         -- 主闭环 issue 编号
    pr_number INTEGER,                 -- 关联的 PR 编号
    spec_ref TEXT,                     -- 执行规范引用
    plan_ref TEXT,                     -- 计划文档引用
    report_ref TEXT,                   -- 报告文档引用
    audit_ref TEXT,                    -- 审计文档引用
    planner_actor TEXT,                -- 规划者身份
    planner_session_id TEXT,           -- 规划会话 ID
    executor_actor TEXT,               -- 执行者身份
    executor_session_id TEXT,          -- 执行会话 ID
    reviewer_actor TEXT,               -- 审查者身份
    reviewer_session_id TEXT,          -- 审查会话 ID
    latest_actor TEXT,                 -- 最后操作者
    blocked_by TEXT,                   -- 阻塞原因
    next_step TEXT,                    -- 下一步动作
    flow_status TEXT NOT NULL DEFAULT 'active',  -- flow 状态
    updated_at TEXT NOT NULL           -- 更新时间
)
```

#### 3.2 `flow_issue_links` 表
关联 flow 与 repo issues（支持多 issue 关联）：
```sql
CREATE TABLE flow_issue_links (
    branch TEXT NOT NULL,              -- Git 分支名
    issue_number INTEGER NOT NULL,     -- Issue 编号
    issue_role TEXT NOT NULL,          -- Issue 角色（'task' / 'related'）
    created_at TEXT NOT NULL,
    PRIMARY KEY (branch, issue_number, issue_role)
)
```

**唯一约束**：每个 flow 只能有一个 `task` issue（主闭环 issue）
```sql
CREATE UNIQUE INDEX idx_flow_single_task_issue
ON flow_issue_links(branch)
WHERE issue_role = 'task'
```

#### 3.3 `flow_events` 表
记录 flow 的事件历史：
```sql
CREATE TABLE flow_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    branch TEXT NOT NULL,              -- Git 分支名
    event_type TEXT NOT NULL,          -- 事件类型
    actor TEXT NOT NULL,               -- 操作者
    detail TEXT,                       -- 事件详情
    created_at TEXT NOT NULL           -- 创建时间
)
```

#### 3.4 `schema_meta` 表
元数据表：
```sql
CREATE TABLE schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
)
```

## 4. 技术要求（分层实现）

### 4.1 Service Layer（Vibe3Store）
**已实现**：`scripts/python/lib/store.py`

提供的核心方法：
- `get_flow_state(branch)` - 获取 flow 状态
- `update_flow_state(branch, **kwargs)` - 更新 flow 状态
- `add_event(branch, event_type, actor, detail)` - 添加事件
- `add_issue_link(branch, issue_number, role)` - 添加 issue 关联
- `get_issue_links(branch)` - 获取 issue 关联
- `get_active_flows()` - 获取所有活跃 flow

### 4.2 Manager Layer（需实现）
需要实现以下 Manager 模块：

#### `scripts/python/vibe3/services/flow_service.py`
- `FlowService` 类，使用 `Vibe3Store` 进行持久化
- 实现方法：
  - `create_flow(slug, branch, task_id)` - 创建新 flow
  - `bind_flow(flow_name, task_id)` - 绑定 task 到 flow
  - `get_flow_status(branch)` - 获取 flow 状态
  - `list_flows(status)` - 列出 flow

#### `scripts/python/vibe3/services/task_service.py`
- `TaskService` 类，使用 `Vibe3Store` 进行持久化
- 实现方法：
  - `create_task(title, spec_ref)` - 创建 task（存入 flow_state）
  - `link_issue(branch, issue_number, role)` - 关联 issue
  - `update_task_status(branch, status)` - 更新 task 状态

### 4.3 Command Layer（需实现）
完善命令实现：

#### `scripts/python/vibe3/commands/flow.py`
- `flow new` - 调用 `FlowService.create_flow()`
- `flow bind` - 调用 `FlowService.bind_flow()`
- `flow status --json` - 调用 `FlowService.get_flow_status()`

#### `scripts/python/vibe3/commands/task.py`
- `task link` - 调用 `TaskService.link_issue()`
- `task show` - 调用 `TaskService.get_task()`

### 4.4 状态转换逻辑
实现 flow 的生命周期状态：
- `new` - 创建 flow，插入 `flow_state` 表
- `bind` - 绑定 task，更新 `flow_state.current_task`
- `status` - 查询 flow，读取 `flow_state` 表

## 5. 成功标准（验收标准）

### 5.1 功能验收
- [ ] `vibe3 flow new test-flow --task 101` 成功插入记录到 `flow_state` 表
- [ ] `vibe3 flow bind task-123` 更新 `flow_state` 表的 `current_task` 字段
- [ ] `vibe3 flow status --json` 返回有效的 JSON，包含 `flow_slug`、`task_issue_number` 等字段
- [ ] `vibe3 task link https://github.com/owner/repo/issues/456` 成功插入记录到 `flow_issue_links` 表

### 5.2 数据库验收
- [ ] 所有数据库事务正确关闭（无连接泄漏）
- [ ] `flow_issue_links` 表的唯一约束生效（每个 flow 只能有一个 task issue）
- [ ] `flow_events` 表正确记录事件

### 5.3 代码质量验收
- [ ] `mypy --strict` 检查通过（无类型错误）
- [ ] Service 层文件 < 300 行
- [ ] Command 层文件 < 100 行
- [ ] 不使用 `print()`，使用 `logger` 或 `rich`

### 5.4 测试验收
- [ ] `FlowService` 单元测试通过（100% 成功率）
- [ ] `TaskService` 单元测试通过（100% 成功率）
- [ ] 核心路径有测试覆盖
- [ ] 测试代码遵循 [04-test-standards.md](../implementation/04-test-standards.md)
  - 测试文件 < 180 行（Services 层）
  - 单个测试函数 < 50 行
  - 使用 Mock 隔离外部依赖
  - 测试覆盖率 >= 80%
  - 使用 pytest fixtures 减少重复代码

### 5.5 架构验收
- [ ] 严格遵循 5 层架构（CLI → Commands → Services → Clients → Models）
- [ ] 不直接在 Command 层执行 SQL 查询
- [ ] 不在 Service 层包含 UI 逻辑