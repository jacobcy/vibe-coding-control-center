---
document_type: plan
title: Phase 02 - Flow & Task State (SQLite)
status: active
author: Claude Sonnet 4.6
created: 2026-03-15
last_updated: 2026-03-20
related_docs:
  - docs/standards/v3/handoff-store-standard.md
  - docs/standards/v3/github-remote-call-standard.md
  - docs/v3/handoff/v3-rewrite-plan.md
  - docs/v3/infrastructure/02-architecture.md
  - docs/v3/infrastructure/03-coding-standards.md
  - docs/v3/infrastructure/04-test-standards.md
  - docs/plans/2026-03-20-pr-command-surface-design.md
---

# Phase 02: Flow & Task State (SQLite)

**Goal**: Implement the state management layer for Flows and Tasks using SQLite, while keeping `pr` as a separate delivery-carrier layer rather than collapsing PR lifecycle into flow/task.

## 1. 架构约束

见 [01-command-and-skeleton.md](01-command-and-skeleton.md) §通用架构约束

## 2. Context Anchor (Optional)

If you require more than technical scope, refer to the [Vibe 3.0 Master Plan](v3-rewrite-plan.md).

## 2. Pre-requisites (Executor Entry)

- [ ] Executor 01 has completed `bin/vibe3` skeleton.
- [ ] `src/vibe_core.py` is accessible.

## 3. 数据库 Schema

见 [handoff-store-standard.md](../../standards/v3/handoff-store-standard.md) §Core Tables

**已实现的表结构**：`src/vibe3/clients/sqlite_client.py`

## 4. 技术要求（分层实现）

### 4.1 Service Layer（Vibe3Store）
**已实现**：`src/vibe3/clients/sqlite_client.py`

提供的核心方法：
- `get_flow_state(branch)` - 获取 flow 状态
- `update_flow_state(branch, **kwargs)` - 更新 flow 状态
- `add_event(branch, event_type, actor, detail)` - 添加事件
- `add_issue_link(branch, issue_number, role)` - 添加 issue 关联
- `get_issue_links(branch)` - 获取 issue 关联
- `get_active_flows()` - 获取所有活跃 flow

### 4.2 Manager Layer（需实现）
需要实现以下 Manager 模块：

#### `src/vibe3/services/flow_service.py`
- `FlowService` 类，使用 `Vibe3Store` 进行持久化
- 实现方法：
  - `create_flow(slug, branch, task_id)` - 创建新 flow
  - `bind_flow(flow_name, task_id)` - 绑定 task 到 flow
  - `get_flow_status(branch)` - 获取 flow 状态
  - `list_flows(status)` - 列出 flow

#### `src/vibe3/services/task_service.py`
- `TaskService` 类，使用 `Vibe3Store` 进行持久化
- 实现方法：
  - `create_task(title, spec_ref)` - 创建 task（存入 flow_state）
  - `link_issue(branch, issue_number, role)` - 关联 issue
  - `update_task_status(branch, status)` - 更新 task 状态

### 4.3 Command Layer（需实现）
完善命令实现：

#### `src/vibe3/commands/flow.py`
- `flow new` - 调用 `FlowService.create_flow()`
- `flow bind` - 调用 `FlowService.bind_flow()`
- `flow status --json` - 调用 `FlowService.get_flow_status()`

#### `src/vibe3/commands/task.py`
- `task link` - 调用 `TaskService.link_issue()`
- `task show` - 调用 `TaskService.get_task()`

### 4.4 状态转换逻辑
实现 flow 的生命周期状态：
- `new` - 创建 flow，插入 `flow_state` 表
- `bind` - 绑定 task，更新 `flow_state.current_task`
- `status` - 查询 flow，读取 `flow_state` 表

### 4.5 PR Command Surface (Finalized)

The PR command surface has been simplified to focus only on delivery-carrier actions with clear project packaging value.

**Public PR Commands (Final)**:
- `pr create` - Create draft PR with project context (task, flow, spec metadata)
- `pr ready` - Mark PR as ready with quality gates (coverage, risk score)
- `pr show` - Show PR status with change analysis and risk summary

**Removed from Public CLI**:
- `pr draft` - Replaced by `pr create`
- `pr merge` - Merge is now handled by `flow done` / `integrate`, not PR command
- `pr version-bump` - No clear project packaging value
- `review-gate` - Removed from this round's cleanup scope

### 4.6 Responsibility Split (Final)

This handoff focuses on flow/task foundation, with PR lifecycle kept separate.

**职责拆分**:

- `task`：吸收 `repo issue`，做 execution record、分合、依赖、主闭环 issue 绑定
- `flow`：把 task 带入 branch 现场，表达当前交付切片
- `pr`：承载当前交付产物，只保留 `create` / `ready` / `show`
- `review`：负责审查动作，不承担 PR 状态切换
- `integrate` / `done`：承担合并与收口，不由 `pr` 直接承载

**主链**:

`repo issue -> task issue -> flow new/bind -> pr create -> pr ready -> review pr -> integrate -> flow done -> close repo issue`

**补充约束**:

- `flow` 不负责 PR ready/merge
- `task` 不负责 PR 创建
- `pr` 不负责 issue intake
- `pr` 不负责 merge (交给 integrate / done / closeout)
- `pre-push` 直接调用 inspect + review，不额外扩张 review gate 命令

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

**测试标准**: 见 [04-test-standards.md](../infrastructure/04-test-standards.md)

### 5.5 架构验收
- [ ] 严格遵循 5 层架构（CLI → Commands → Services → Clients → Models）
- [ ] 不直接在 Command 层执行 SQL 查询
- [ ] 不在 Service 层包含 UI 逻辑
