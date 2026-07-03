# Feature Specification: Role Protocol Baseline

**Feature Branch**: `dev/issue-3299`

**Created**: 2026-07-03

**Status**: Draft (Baseline / Reverse Specification)

**Spec Mode**: 逆向规格化（Reverse Specification）。本 spec 描述 role 协议子系统**当前代码的行为契约**，作为后续变更的行为参照基线。**不设计新功能、不改代码。**

**Input**: User description: "逆向规格化 role-protocol 模块的现有行为契约（baseline spec，非新功能设计）"

## Spec Mode 说明

本 spec 是 **baseline 行为契约**，描述"系统现在如何用触发条件 + 输入输出契约 + 执行模式定义各角色"。代码真源：

- `src/vibe3/roles/*`（definitions / registry / manager / plan / run / review / governance / supervisor）
- `src/vibe3/config/role_policy.py`（`RoleOutputContract` / `ROLE_OUTPUT_CONTRACTS`）
- `config/v3/review_kernel.yaml`（review_floor 审查等级）
- `src/vibe3/models/orchestration.py`（`ALLOWED_TRANSITIONS` / 状态机）

**冲突处理**：当代码现状与文档/issue 描述不一致时，本 spec 以代码行为为准并显式标注差异。**范围边界**：本 spec 不承载项目硬规则，仅引用 [CLAUDE.md](../../../CLAUDE.md) §HARD RULES、[docs/standards/glossary.md](../../../docs/standards/glossary.md)、[docs/standards/v3/human-mirror-architecture-philosophy.md](../../../docs/standards/v3/human-mirror-architecture-philosophy.md)、[.specify/memory/constitution.md](../../memory/constitution.md)。

**关联 spec**：与 [002-dispatch-execution](../002-dispatch-execution/spec.md) 协作——role 定义触发条件，dispatch 据此发事件；与 [001-flow-lifecycle](../001-flow-lifecycle/spec.md) 协作——role 输出契约被 no-op gate 消费。

## 关于 "L1/L2/L3 执行等级" 的诚实记录

issue #3299 描述本 spec 要点含"L1/L2/L3 执行等级"。**role 协议层不存在名为 L1/L2/L3 的显式分层**（注：environment 层有 L2/L3 worktree 层级——L3 issue-bound / L2 temporary，见 [004-environment-isolation](../004-environment-isolation/spec.md)——但那是物理隔离层级，非 role 执行等级）。在 role 协议层，实际定义角色"执行等级"的机制是以下三者的组合，本 spec 如实描述：

1. **`review_floor`**（[config/v3/review_kernel.yaml](../../../config/v3/review_kernel.yaml)）：针对 runtime/orchestra 核心文件的审查等级（如 `repeated`），由 review kernel 在审查时强制。
2. **执行模式**（sync / async）：governance/supervisor 走同步；plan/run/review 走异步（见 002 FR-008）。
3. **`RoleOutputContract`**（required_ref / requires_verdict）：角色输出硬契约，由 no-op gate 强制。

若未来需要引入显式 L1/L2/L3 执行等级，属于新设计（走 constitution 原则 I 的 spec-before-code），不在本 baseline 范围。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Label 触发的角色分发 (Priority: P1)

issue 的 `state/*` label 变化触发对应 role：`READY→manager`、`CLAIMED→planner`、`IN_PROGRESS→executor`、`MERGE_READY→executor-publish`、`REVIEW→reviewer`、`HANDOFF→manager-handoff`。`BLOCKED` 不直接 dispatch（由 qualify gate 内部处理）。

**Why this priority**: label→role 映射是编排系统的核心协议表，决定每个 issue 状态由谁处理。

**Independent Test**: 对一个 `state/claimed` issue 触发 label dispatch，验证 `PLANNER_ROLE` 被选中并发布 `PlannerDispatchIntent`。

**Acceptance Scenarios**:

1. **Given** issue 处于 `state/ready`，**When** label dispatch 触发，**Then** `MANAGER_ROLE`（trigger_state=READY）被选中，发布 `ManagerDispatchIntent`。
2. **Given** issue 处于 `state/claimed`，**When** dispatch，**Then** `PLANNER_ROLE` 发布 `PlannerDispatchIntent`（trigger_state 强制为 CLAIMED）。
3. **Given** issue 处于 `state/in-progress`，**When** dispatch，**Then** `EXECUTOR_ROLE` 发布 `ExecutorDispatchIntent`。
4. **Given** issue 处于 `state/review`，**When** dispatch，**Then** `REVIEWER_ROLE` 发布 `ReviewerDispatchIntent`。
5. **Given** issue 处于 `state/blocked`，**When** 尝试 dispatch，**Then** `BLOCKED_ROLE` 抛 `ValueError`（不直接 dispatch，由 qualify gate 处理解阻推断）。

---

### User Story 2 - 角色输出契约（RoleOutputContract）(Priority: P1)

每个 role 声明其输出契约：planner 必须产出 `plan_ref`；reviewer 必须产出 `latest_verdict`；executor/manager 无强制 ref。契约由 no-op gate 在 agent 完成后强制（见 002 FR-004）。

**Why this priority**: 输出契约是判定角色"是否真正完成"的硬标准，直接驱动 block/pass 决策。

**Independent Test**: 构造 planner 执行后 `flow_state.plan_ref` 为空的场景，验证 no-op gate 调用 planner 的 block 函数。

**Acceptance Scenarios**:

1. **Given** `PLANNER_ROLE.output_contract = RoleOutputContract(required_ref="plan_ref")`，**When** planner 完成后 `flow_state.plan_ref` 缺失，**Then** no-op gate block 该 flow。
2. **Given** `REVIEWER_ROLE.output_contract = RoleOutputContract(requires_verdict=True)`，**When** reviewer 完成后 `latest_verdict` 缺失，**Then** no-op gate block。
3. **Given** `EXECUTOR_ROLE` / `MANAGER_ROLE`（无 required_ref、无 requires_verdict），**When** 这些角色完成，**Then** no-op gate 仅检查 state label 是否变化（不检查 ref）。
4. **Given** 任意 role 名查询 `get_role_output_contract(role)`，**When** role 未在 `ROLE_OUTPUT_CONTRACTS` 注册，**Then** 返回空契约（无要求，fail-open）。

---

### User Story 3 - Manager 角色双触发（READY 与 HANDOFF）(Priority: P2)

manager 由两个 `TriggerableRoleDefinition` 覆盖：`MANAGER_ROLE`（trigger_state=READY，派发创建 flow）与 `HANDOFF_MANAGER_ROLE`（trigger_state=HANDOFF，处理 handoff 决策如发布 PR 或收尾）。

**Why this priority**: manager 是唯一有多个 trigger_state 的角色，契约需明确"同一 registry_role、不同 trigger_state"的分工。

**Independent Test**: 对 READY 与 HANDOFF 两个状态分别触发，验证两个 manager 角色实例各自响应。

**Acceptance Scenarios**:

1. **Given** issue 处于 `state/ready`，**When** dispatch，**Then** `MANAGER_ROLE` 响应（创建 flow、bootstrap）。
2. **Given** issue 处于 `state/handoff`，**When** dispatch，**Then** `HANDOFF_MANAGER_ROLE` 响应（handoff 决策：发布 PR 或收尾）。
3. **Given** 两个 manager role 实例，**When** 检查 `registry_role`，**Then** 二者均为 `"manager"`（同一底层角色，不同触发面）。

---

### User Story 4 - Executor 角色双触发（IN_PROGRESS 与 MERGE_READY）(Priority: P2)

executor 由 `EXECUTOR_ROLE`（trigger_state=IN_PROGRESS，方案执行）与 `EXECUTOR_PUBLISH_ROLE`（trigger_state=MERGE_READY，发布 PR）覆盖。

**Why this priority**: executor 的执行与发布是两个独立阶段，需明确触发分工。

**Independent Test**: 对 IN_PROGRESS 与 MERGE_READY 分别触发，验证 executor 与 executor-publish 各自响应。

**Acceptance Scenarios**:

1. **Given** issue 处于 `state/in-progress`，**When** dispatch，**Then** `EXECUTOR_ROLE` 响应（方案执行）。
2. **Given** issue 处于 `state/merge-ready`，**When** dispatch，**Then** `EXECUTOR_PUBLISH_ROLE` 响应（发布 PR）。

---

### User Story 5 - Governance / Supervisor 非 label 触发 (Priority: P3)

governance（治理扫描、roadmap 建议）与 supervisor（异常监控恢复）**不**在 `LABEL_DISPATCH_ROLES` 中，由 CLI 或 scheduled 触发（`scan_service.py`、supervisor 调度），走同步执行路径。

**Why this priority**: 这两个角色是"非常规"label 角色，契约需明确其触发方式与执行模式差异。

**Independent Test**: 通过 CLI（如 `vibe3 scan`）触发 governance，验证同步执行 + 不经过 label dispatch。

**Acceptance Scenarios**:

1. **Given** governance 扫描任务，**When** 通过 `scan_service` / CLI 触发，**Then** 走同步执行（`governance_sync_runner`），不发布 label dispatch 事件。
2. **Given** supervisor 监控任务，**When** 由 scheduled 或 CLI 触发，**Then** 执行异常监控与恢复逻辑，不经 label dispatch。

---

### User Story 6 - Review Kernel 审查等级（review_floor）(Priority: P3)

`config/v3/review_kernel.yaml` 为 runtime/orchestra 核心文件登记审查等级（如 `repeated`），reviewer 角色与 review 流程据此对核心文件施加更高审查强度。

**Why this priority**: review_floor 是代码审查层面的"等级"机制，是 issue 所述"执行等级"在代码中最接近的对应物。

**Independent Test**: 修改一个 review_kernel.yaml 登记文件，验证 review 流程施加对应 review_floor。

**Acceptance Scenarios**:

1. **Given** `review_kernel.yaml` 为 `src/vibe3/runtime/heartbeat.py` 登记 `review_floor: repeated`，**When** reviewer 审查涉及该文件的变更，**Then** 按 `repeated` 等级施加审查强度。
2. **Given** 未在 review_kernel.yaml 登记的文件，**When** reviewer 审查，**Then** 按默认审查等级处理。

---

### Edge Cases

- **`TriggerName` 受限集合**：`Literal["manager", "plan", "run", "review", "blocked"]`；`build_label_dispatch_event` 对未支持的 trigger 抛 `ValueError`。
- **RoleOutputContract 镜像**：`ROLE_OUTPUT_CONTRACTS` 在 `config/role_policy.py` 镜像各 role 的 `output_contract`，目的是让 `noop_gate` 按角色名字符串查契约**无需 import roles/**（打破 `roles/plan.py → execution/codeagent_runner.py → execution/noop_gate.py` 循环）。两处定义必须保持一致。
- **frozen dataclass**：`RoleDefinition` / `TriggerableRoleDefinition` / `IssueRoleSyncSpec` 均为 `frozen=True`，角色定义为不可变单例。
- **WorktreeRequirement**：每个 role 通过 `*_GATE_CONFIG` 声明 worktree 需求（manager/executor 需要 worktree，blocked 为 `"none"`），由 execution 层据此分配资源。
- **governance/supervisor 的同步性**：二者不参与 label dispatch，不受 `LABEL_DISPATCH_ROLES` 约束，契约通过其专用入口（`scan_service`、supervisor scheduler）定义。
- **roles 不直接 import domain**（循环依赖，见 002 FR-013）：roles 通过 `vibe3.execution` 公开 API 与 `services/flow`、`services/shared/events` 间接消费 domain。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系统 MUST 通过 `LABEL_DISPATCH_ROLES` 元组定义 label-triggered 角色：`MANAGER_ROLE` / `HANDOFF_MANAGER_ROLE` / `PLANNER_ROLE` / `EXECUTOR_ROLE` / `EXECUTOR_PUBLISH_ROLE` / `REVIEWER_ROLE` / `BLOCKED_ROLE`。
- **FR-002**: 每个非 blocked role MUST 声明 `trigger_name ∈ {manager, plan, run, review}` 与 `trigger_state ∈ IssueState`；`BLOCKED_ROLE` 的 `trigger_name="blocked"` 且不可直接 dispatch（`build_label_dispatch_event` 抛 `ValueError`）。
- **FR-003**: `build_label_dispatch_event(role, issue, branch)` MUST 按 `trigger_name` 发布对应 neutral intent（`ManagerDispatchIntent` / `PlannerDispatchIntent` / `ExecutorDispatchIntent` / `ReviewerDispatchIntent`），不在 dispatch 层读取执行上下文（refs、commit_mode），由 handler 层 enrich。
- **FR-004**: `PLANNER_ROLE` 输出契约 MUST 为 `required_ref="plan_ref"`；`REVIEWER_ROLE` MUST 为 `requires_verdict=True`；`EXECUTOR_ROLE` / `MANAGER_ROLE` / `HANDOFF_MANAGER_ROLE` / `EXECUTOR_PUBLISH_ROLE` / `BLOCKED_ROLE` 为空契约（无 required_ref、无 requires_verdict）。
- **FR-005**: `ROLE_OUTPUT_CONTRACTS`（`config/role_policy.py`）MUST 与各 role 实例的 `output_contract` 镜像一致，供 `noop_gate` 按角色名字符串查契约而无需 import roles（打破循环依赖）。
- **FR-006**: `get_role_output_contract(role)` 对未注册 role 名 MUST 返回空契约（fail-open，不抛错）。
- **FR-007**: manager MUST 由两个 TriggerableRoleDefinition 覆盖：`MANAGER_ROLE`（trigger_state=READY）与 `HANDOFF_MANAGER_ROLE`（trigger_state=HANDOFF），二者 `registry_role="manager"`。
- **FR-008**: executor MUST 由 `EXECUTOR_ROLE`（trigger_state=IN_PROGRESS）与 `EXECUTOR_PUBLISH_ROLE`（trigger_state=MERGE_READY）覆盖，二者 `registry_role="executor"`。
- **FR-009**: planner 固定 trigger_state=CLAIMED；reviewer 固定 trigger_state=REVIEW（由 `build_label_dispatch_event` 强制）。
- **FR-010**: governance 与 supervisor MUST NOT 出现在 `LABEL_DISPATCH_ROLES`；二者由 CLI / scheduled 触发，走同步执行（见 002 FR-008）。
- **FR-011**: `review_kernel.yaml` MUST 为核心文件登记 `review_floor`（如 `repeated`）；reviewer 据此对登记文件施加对应审查强度。
- **FR-012**: 所有角色定义 MUST 为 `frozen=True` dataclass（不可变单例），不持有外部资源。
- **FR-013**: `IssueRoleSyncSpec` MUST 封装角色自有 hooks（`resolve_options` / `resolve_branch` / `build_async_request` / `build_sync_request` / 可选 `failure_handler`），供通用 issue sync runner 使用。
- **FR-014**: roles MUST NOT 直接 import `vibe3.domain`（循环依赖）；仅通过 `vibe3.execution` 公开 API 与 `services/flow`、`services/shared/events` 间接消费 domain 事件。

### Key Entities *(include if feature involves data)*

- **RoleDefinition**：角色最小声明（name / registry_role / worktree 需求 / trigger / output_contract），`frozen=True`。
- **TriggerableRoleDefinition**：带强制 trigger 字段的 RoleDefinition（trigger_name / trigger_state），用于 label dispatch。
- **IssueRoleSyncSpec**：角色自有 hooks 集合，供通用 sync runner 调用。
- **RoleOutputContract**：输出契约（`required_ref: str | None`、`requires_verdict: bool`）。
- **LABEL_DISPATCH_ROLES**：label-triggered 角色元组（7 个），是 dispatch 协议表。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `LABEL_DISPATCH_ROLES` 的 7 个角色与 `build_label_dispatch_event` 支持的 trigger 名集合一致，且 BLOCKED_ROLE 直接 dispatch 抛 `ValueError`（可测试）。
- **SC-002**: `ROLE_OUTPUT_CONTRACTS` 镜像与各 role 实例 `output_contract` 一致（一致性测试可机器验证）。
- **SC-003**: planner 缺 `plan_ref` / reviewer 缺 verdict 时 no-op gate block（与 002 SC-001 联合验证）。
- **SC-004**: manager 双 trigger_state（READY/HANDOFF）与 executor 双 trigger_state（IN_PROGRESS/MERGE_READY）各自有独立 dispatch 测试覆盖。
- **SC-005**: governance/supervisor 不在 `LABEL_DISPATCH_ROLES` 且不发布 label dispatch 事件（可机器验证）。
- **SC-006**: roles 模块对 `vibe3.domain` 的直接 import 为零（循环依赖约束可机器验证，与 002 SC-006 一致）。

## Assumptions

- **baseline 范围假设**：本 spec 覆盖角色定义、触发条件、输出契约、label dispatch 映射、governance/supervisor 触发方式、review_floor。**不**覆盖 dispatch 协调器内部（见 002）、flow 状态语义（见 001）、prompt 模板组装（属 prompts 模块，P2 后续）。
- **"L1/L2/L3 执行等级"假设**：代码中无此显式分层；实际"等级"由 review_floor + sync/async + RoleOutputContract 共同定义。引入显式 L1/L2/L3 属新设计，不在本 baseline。
- **角色权力边界假设**：manager/planner/executor/reviewer/governance/supervisor 的权力边界与制衡由 [docs/standards/v3/human-mirror-architecture-philosophy.md](../../../docs/standards/v3/human-mirror-architecture-philosophy.md) 定义，本 spec 描述触发/契约机制，不复述权力边界内容。
- **不可变单例假设**：所有角色定义为 `frozen=True` dataclass 预构建单例，符合 [modularity-standards.md](../../../.claude/rules/modularity-standards.md) Singleton 导出规范。
