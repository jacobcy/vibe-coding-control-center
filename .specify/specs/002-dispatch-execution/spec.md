# Feature Specification: Dispatch Execution Baseline

**Feature Branch**: `dev/issue-3299`

**Created**: 2026-07-03

**Status**: Draft (Baseline / Reverse Specification)

**Spec Mode**: 逆向规格化（Reverse Specification）。本 spec 描述 dispatch-execution 子系统**当前代码的行为契约**，作为后续变更的行为参照基线。**不设计新功能、不改代码。**

**Input**: User description: "逆向规格化 dispatch-execution 模块的现有行为契约（baseline spec，非新功能设计）"

## Spec Mode 说明

本 spec 是 **baseline 行为契约**，描述"系统现在如何 dispatch 与执行角色"。代码真源：

- `src/vibe3/execution/*`（coordinator / capacity_service / noop_gate / *_runner / actor / job_monitor_service / session_service 等）
- `src/vibe3/domain/dispatch_*.py`（dispatch_coordinator / dispatch_lifecycle / dispatch_preflight / dispatch_health / dispatch_queue_*）
- `src/vibe3/domain/handlers/dispatch.py` / `manual_dispatch.py` / `issue_state_dispatch.py`

**冲突处理**：当代码现状与文档不一致时，本 spec 以代码行为为准并显式标注差异。**范围边界**：本 spec 不承载项目硬规则，仅引用 [CLAUDE.md](../../../CLAUDE.md) §HARD RULES、[docs/standards/v3/event-driven-standard.md](../../../docs/standards/v3/event-driven-standard.md)、[.specify/memory/constitution.md](../../memory/constitution.md)。

**关联 spec**：与 [001-flow-lifecycle](../001-flow-lifecycle/spec.md) 协作——dispatch 触发 flow 状态转换；与 [003-role-protocol](../003-role-protocol/spec.md) 协作——execution 执行 role 请求。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 事件驱动分发（DispatchIntent → 角色执行）(Priority: P1)

`PlannerDispatchIntent` / `ExecutorDispatchIntent` / `ReviewerDispatchIntent` 事件由对应 handler 接收，转译为 `ExecutionRequest`，经 `ExecutionCoordinator.dispatch_execution` 完成「容量检查 → worktree/session 分配 → sync/async 分发」全链路。

**Why this priority**: 事件驱动分发是整个编排系统的主循环入口；契约最完整、覆盖 plan/run/review 三大角色。

**Independent Test**: 发布一个 `PlannerDispatchIntent` 事件，观察 `handle_planner_dispatch_intent` → `dispatch_execution` 调用链，验证容量检查通过时执行启动、容量满时被跳过。

**Acceptance Scenarios**:

1. **Given** 全局 live session 数 < `max_concurrent_flows`，**When** `PlannerDispatchIntent` 发布，**Then** `handle_planner_dispatch_intent` 触发 `dispatch_execution`，worktree/session 分配后角色执行启动。
2. **Given** 全局 live session 数 ≥ `max_concurrent_flows`，**When** 任一 `DispatchIntent` 发布，**Then** `CapacityService.can_dispatch(role)` 返回 False，dispatch 被跳过并记录 capacity 原因日志（`live=N, max=M`）。
3. **Given** 一个 `ManualRunIntent`（人工触发），**When** `manual_dispatch` handler 接收，**Then** 走与自动 dispatch 相同的 `dispatch_execution` 入口（统一执行路径）。

---

### User Story 2 - No-op 门控跳过无意义执行 (Priority: P1)

agent 完成后，`apply_unified_noop_gate` 检查角色是否真正推进了状态机；未推进则 block（而非计入完成），避免空转被误判为成功。

**Why this priority**: no-op gate 是防止 agent "假完成"的硬门控；其 5 条规则的正确性直接决定编排可信度（依据 PR #3282 类 dispatch 缺陷均源于状态判定不一致）。

**Independent Test**: 构造 agent 未改变 state/ label 的场景，验证 noop gate 调用 role 的 block 函数将 flow 标记 blocked。

**Acceptance Scenarios**:

1. **Given** issue 无任何 `state/` label，**When** noop gate 运行，**Then** SKIP（日志 "No-op gate SKIP: issue has no state/ label"），不判定 pass/block。
2. **Given** 角色的 `required_ref` 缺失于 `flow_state`（如 review 缺 `audit_ref`），**When** noop gate 运行，**Then** 调用 role block 函数，flow 标记 blocked。
3. **Given** 角色要求 verdict 但 `latest_verdict` 缺失，**When** noop gate 运行，**Then** block。
4. **Given** agent 执行前后 issue 的 `state/` label 集合未变，**When** noop gate 运行，**Then** block（state 未变）。
5. **Given** agent 执行前后 state label 集合发生变化（或 issue 由 open → closed），**When** noop gate 运行，**Then** 记录 transition 事件并通过。

---

### User Story 3 - Dispatch 生命周期 FSM（ACTIVE/SLEEPING）(Priority: P2)

dispatch 主循环采用两态有限状态机：连续 `idle_threshold_ticks` 个空闲 tick 后 `ACTIVE → SLEEPING`；SLEEPING 态仅在 scheduled refresh ticks collect，节省 GitHub API 配额。

**Why this priority**: SLEEPING 是系统在无活动时的资源节约模式，契约需明确状态迁移条件与 collect 行为差异。

**Independent Test**: 模拟连续 idle tick 达到阈值，验证 FSM 进入 SLEEPING；模拟 scheduled refresh tick，验证 SLEEPING 态仍 collect。

**Acceptance Scenarios**:

1. **Given** FSM 处于 ACTIVE 且连续空闲 tick 达到 `idle_threshold_ticks`，**When** 下一个 tick 到达，**Then** `ACTIVE → SLEEPING`。
2. **Given** FSM 处于 SLEEPING，**When** scheduled refresh tick 到达，**Then** 触发 collect（而非每个 tick 都 collect）。
3. **Given** FSM 处于 SLEEPING 且检测到有待处理活动，**When** 活动信号到达，**Then** `SLEEPING → ACTIVE`（恢复每 tick collect）。

---

### User Story 4 - Dispatch Preflight 资格检查 (Priority: P2)

`DispatchPreflightService.evaluate` 在实际派发前对 issue 做资格判定（`qualify_blocked` / `qualify_active`），决定是否进入派发或需先解阻。

**Why this priority**: preflight 是 dispatch 的前置守门，避免对 blocked/无资格 issue 的无效派发。

**Independent Test**: 对一个 blocked issue 调用 `evaluate`，验证返回需先解阻的决策；对一个 active issue 验证放行。

**Acceptance Scenarios**:

1. **Given** issue 处于 blocked 状态，**When** `DispatchPreflightService.evaluate(issue)` 运行，**Then** `qualify_blocked` 判定是否可推断恢复 label。
2. **Given** issue 处于 active 状态，**When** `evaluate` 运行，**Then** `qualify_active` 判定是否满足派发条件（assignee pool、容量等）。

---

### User Story 5 - 依赖解除触发重新评估（IssueResolvedDependency）(Priority: P2)

当一个被依赖的 issue 关闭，`IssueResolvedDependency` 事件触发对依赖它的 blocked flow 的重新评估（PR #3286），使原本因依赖阻塞的 flow 有机会自动解封。

**Why this priority**: 这是跨 issue 编排的自动唤醒机制，契约需明确"依赖解除 → 重新评估 → 可能解封"链路。

**Independent Test**: 构造 flow A 依赖 issue B（B 阻塞 A），关闭 B 后发布 `IssueResolvedDependency`，验证 A 的 `reconcile_blocked` 被触发并解封。

**Acceptance Scenarios**:

1. **Given** flow A 因 `blocked_by_issue=B` 阻塞且无手工 `blocked_reason`，**When** issue B 关闭并发布 `IssueResolvedDependency`，**Then** A 的阻塞被重新评估，依赖满足后自动解封（推断恢复 label）。
2. **Given** flow A 既有 `blocked_reason` 又依赖 B，**When** B 关闭，**Then** 重新评估仍判定 blocked（手工 reason 阻止自动解封，与 001 FR-006 一致）。

---

### User Story 6 - Sync vs Async 执行模式 (Priority: P3)

governance 扫描、supervisor 检查、issue 角色执行走同步路径（阻塞当前线程）；复杂 plan/run 流程走异步路径（启动后台进程，立即返回）。

**Why this priority**: 双模式覆盖长短任务，契约需明确各 role 的默认模式与资源回收差异。

**Independent Test**: 触发 governance 同步执行验证阻塞完成；触发 plan 异步执行验证立即返回 + 后台 job 追踪。

**Acceptance Scenarios**:

1. **Given** governance 扫描任务，**When** 经 `governance_sync_runner` 执行，**Then** 同步阻塞至完成，结果直接返回。
2. **Given** 复杂 plan 流程，**When** 经异步启动器分发，**Then** 立即返回 launch result，后台 job 由 `JobMonitorService` 持久化追踪，支持跨重启恢复。

---

### Edge Cases

- **资源隔离**：每次执行 MUST 在独立 worktree + session 中；`_acquire_temporary_worktree` 为无 flow 绑定的临时执行分配 worktree。
- **Actor TTL 清理**：`ActorRegistry.cleanup_expired()` 清理超时 actor，防止僵尸 worker 累积。
- **Job 跨重启恢复**：`JobMonitorService` 持久化 `record_start` / `record_completion`，重启后 `get_active_jobs` 可恢复未完成 job 快照。
- **roles 不直接 import domain**（循环依赖约束）：roles 通过 `vibe3.execution` 公开 API 调用执行层，通过 `services/flow/factory.py`（`create_flow_manager`）与 `services/shared/events.py`（`emit_issue_failed`）间接消费 domain 事件。
- **services 层不反向依赖 execution**：`CapacityService` 依赖 `services.flow.FlowService` 查询活跃 flow 数；`CodeagentExecutionService` 依赖 `services.orchestra.ErrorTrackingService` 记录错误；反向依赖禁止。
- **transition_count 循环防护**：与 001 共享的 `transition_count` 防止 dispatch→block→dispatch 在同一 flow 上无限震荡。
- **backend 注入**：`ExecutionCoordinator` 通过 `BackendProtocol` 依赖注入支持不同 agent backend（CodeagentBackend 等），不硬编码后端。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `PlannerDispatchIntent` / `ExecutorDispatchIntent` / `ReviewerDispatchIntent` / `Manual*Intent` 事件 MUST 由 `handlers/dispatch.py` / `manual_dispatch.py` 对应 handler 接收，统一转译为 `ExecutionRequest` 并调用 `ExecutionCoordinator.dispatch_execution`。
- **FR-002**: `dispatch_execution` MUST 按序完成：no-op 门控 → 容量检查 → worktree/session 分配 → 执行上下文构建 → sync/async 启动 → 监控 → 资源回收。
- **FR-003**: `CapacityService.can_dispatch(role)` MUST 基于 live session count 与 `config.max_concurrent_flows` 判定；容量满时返回 False 并记录 `live=N, max=M` 日志，dispatch 被跳过（非排队）。
- **FR-004**: `apply_unified_noop_gate` MUST 按 5 条规则判定：无 `state/` label → SKIP；`required_ref` 缺失 → block；要求 verdict 但 `latest_verdict` 缺失 → block；state label 集合未变 → block；state 变化或 issue 由 open→closed → pass。
- **FR-005**: dispatch 生命周期 MUST 采用 `ACTIVE`/`SLEEPING` 两态 FSM：连续 `idle_threshold_ticks` 个空闲 tick → SLEEPING；SLEEPING 仅在 scheduled refresh ticks collect；检测到活动 → ACTIVE。
- **FR-006**: `DispatchPreflightService.evaluate(issue)` MUST 在派发前运行 `qualify_blocked` / `qualify_active` 资格判定，拒绝无资格 issue 进入派发。
- **FR-007**: `IssueResolvedDependency` 事件 MUST 触发对依赖该 issue 的 blocked flow 的 `reconcile_blocked` 重新评估；自动解封仅在"无手工 reason 且依赖全部满足"时发生（与 001 FR-008 一致）。
- **FR-008**: governance/supervisor/issue 角色 MUST 走同步执行（`governance_sync_runner` / `issue_role_sync_runner`），阻塞至完成；复杂 plan/run MUST 走异步执行，立即返回并由 `JobMonitorService` 持久化追踪。
- **FR-009**: 每次执行 MUST 在独立 worktree + session 中运行（资源隔离）；`SessionRegistryService` 管理 session 生命周期。
- **FR-010**: `ActorRegistry` MUST 提供 worker 抽象与 TTL 自动清理（`cleanup_expired`）；`JobMonitorService` MUST 持久化 `record_start`/`record_completion`，支持跨重启 `get_active_jobs` 恢复。
- **FR-011**: `ExecutionCoordinator` MUST 通过 `BackendProtocol` 依赖注入 agent backend，不硬编码具体后端；`CommandAdapterRegistry` 将不同后端适配为统一接口。
- **FR-012**: 执行失败 MUST 通过 `services.shared.events.emit_issue_failed` 发布 `IssueFailed` 事件，并经 `ErrorTrackingService` 计入 `error_log`（ERROR 系统，与 001 FR-004 正交）。
- **FR-013**: roles MUST NOT 直接 import domain（循环依赖约束），仅通过 `vibe3.execution` 公开 API 与 `services/flow`、`services/shared/events` 间接消费 domain。
- **FR-014**: services 层 MUST NOT 反向依赖 execution（依赖方向：execution → services 单向）。

### Key Entities *(include if feature involves data)*

- **ExecutionRequest**：角色执行请求（role、issue、branch、prompt 上下文、cwd 等），`contracts.py` 定义。
- **ExecutionLaunchResult**：`dispatch_execution` 返回值（启动结果、job_id 等）。
- **DispatchState**（FSM）：`ACTIVE` / `SLEEPING`，由 `dispatch_lifecycle.py` 的两态机管理。
- **DispatchPreflightDecision**：preflight 资格判定结果。
- **CapacityStatus**：`{active_count, max_capacity, remaining}`，由 `CapacityService.get_capacity_status` 返回。
- **ActorRegistry / JobMonitor**：worker 监督与 job 持久化实体。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 5 条 no-op gate 规则各自有独立单元测试覆盖（SKIP / required_ref 缺失 / verdict 缺失 / state 未变 / state 变化 pass）。
- **SC-002**: `CapacityService.can_dispatch` 在 live session 数达到 `max_concurrent_flows` 时返回 False，且 dispatch 不启动执行（可测试验证）。
- **SC-003**: `IssueResolvedDependency` 事件触发后，依赖它的 blocked flow（无手工 reason）的 `reconcile_blocked` 被调用并可自动解封（集成测试可验证）。
- **SC-004**: dispatch FSM 在连续 `idle_threshold_ticks` 空闲后进入 SLEEPING，SLEEPING 态 collect 频率低于 ACTIVE 态（可观测 GitHub API 调用减少）。
- **SC-005**: 异步执行启动后 `JobMonitorService.record_start` 被调用，重启后 `get_active_jobs` 能恢复该 job 快照。
- **SC-006**: roles 模块对 `vibe3.domain` 的直接 import 在依赖图检查中为零（循环依赖约束可机器验证）。

## Assumptions

- **baseline 范围假设**：本 spec 覆盖 dispatch 事件分发、容量控制、no-op 门控、FSM 生命周期、preflight、依赖解除重评估、sync/async 模式、actor/job 监督。**不**覆盖 role 内部协议细节（见 003-role-protocol）、flow 状态语义（见 001-flow-lifecycle）、worktree 物理管理（见 004-environment-isolation）。
- **容量模型假设**：当前 `CapacityService` 基于 live session count 的简单模型（`max_concurrent_flows` 全局上限），未实现按 role 差异化配额或排队队列（dispatch 满即跳过，非排队等待）。
- **依赖方向假设**：execution → services 单向；roles 通过 execution + services 间接消费 domain，不直接 import domain。这些由 [execution/README.md](../../../src/vibe3/execution/README.md) 与 [docs/standards/v3/event-driven-standard.md](../../../docs/standards/v3/event-driven-standard.md) 定义，本 spec 引用不复述。
- **no-op gate 假设**：no-op gate 是 agent 完成后的硬门控，与 flow block（001 FR-005）协作——gate 判定 block 时调用 role 的 block 函数写入 `blocked_reason`。
