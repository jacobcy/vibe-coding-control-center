# Feature Specification: Flow Lifecycle Baseline

**Feature Branch**: `dev/issue-3299`

**Created**: 2026-07-03

**Status**: Draft (Baseline / Reverse Specification)

**Spec Mode**: 逆向规格化（Reverse Specification）。本 spec 描述 flow-lifecycle 子系统**当前代码的行为契约**，作为后续变更的行为参照基线。**不设计新功能、不改代码。**

**Input**: User description: "逆向规格化 flow-lifecycle 模块的现有行为契约（baseline spec，非新功能设计）"

## Spec Mode 说明

本 spec 是 **baseline 行为契约**（描述"系统现在如何行为"），不是新功能需求。与以下真源的关系：

- **目标规范真源**：[docs/standards/flow-lifecycle-standard.md](../../../docs/standards/flow-lifecycle-standard.md) 定义"系统应当如何"。本 spec 描述"系统实际如何"。
- **代码真源**：`src/vibe3/services/flow/*`、`src/vibe3/models/flow.py`、`src/vibe3/models/state_machine.py`、`src/vibe3/models/orchestration.py`。
- **冲突处理**：当代码现状与 standard 文档不一致时，本 spec 以代码行为为准并显式标注差异；规范演进走 [SOUL.md](../../../SOUL.md) 文档维护流程，不在本 spec 内发明。
- **范围边界**：本 spec **不承载**项目硬规则与术语定义，仅引用 [CLAUDE.md](../../../CLAUDE.md) §HARD RULES、[docs/standards/glossary.md](../../../docs/standards/glossary.md)、[.specify/memory/constitution.md](../../memory/constitution.md)。

## User Scenarios & Testing *(mandatory)*

> 下列 "用户故事" 在 baseline 语境下指**系统当前可观察的行为路径**，每条可独立通过现有命令或事件观测复现。"Priority" 在此表示该路径在日常运行中的出现频度与契约重要性。

### User Story 1 - 正常完成路径（Issue → PR merged → done）(Priority: P1)

一个绑定到 `task/issue-N` 分支的 flow，在 agent 执行完成并发布 PR、PR 被 merge 后，flow 进入 `done` 终态，物理资源随后由清理流程回收，flow 记录保留用于审计。

**Why this priority**: 这是 flow 的"幸福路径"，是整个编排系统的价值闭环；契约最完整、触发最频繁。

**Independent Test**: 在测试仓库创建 issue、bootstrap flow、手动模拟 PR merged 事件，观察 `flow_status` 由 `active` 经 `review`/`merge-ready` 到 `done`，且 `close_issue_if_open` 恰好在多 flow 绑定解除时关闭 task issue。

**Acceptance Scenarios**:

1. **Given** issue #123 仅绑定 `task/issue-123` 一个 active flow 且 PR 已 created，**When** PR merged webhook 触发，**Then** `flow_status` → `done`，task issue 被关闭（`close_issue_if_open` 返回 `closed` 或 `already_closed`）。
2. **Given** issue #123 同时绑定 `task/issue-123` 与 `dev/issue-123` 两个 active flow，**When** 仅 `task/issue-123` 的 PR merged，**Then** 该 flow → `done`，但 issue #123 **不**关闭（多 flow 保护），需待另一 flow 也 `done`。
3. **Given** 一个 `done` flow，**When** `vibe3 check --clean-branch` 执行，**Then** 物理资源（worktree/branch/handoff）被回收，flow 记录**保留**（`deleted_at` 保持 NULL）。

---

### User Story 2 - 派发失败阻塞（block by reason）(Priority: P1)

agent 执行失败、health check 失败或人工标记需要关注时，flow 进入 `blocked` 状态，阻塞原因写入 `blocked_reason`，task issue label 转为 `state/blocked`，需人工或自动路径恢复。

**Why this priority**: 阻塞是编排系统最常见的非终态偏离路径；`block` 的原子副作用与解封条件是契约核心。

**Independent Test**: 触发 `BlockedStateService.set_block(...)`，验证 SQLite（`blocked_reason`）、GitHub issue body 投影、`state/blocked` label、`flow_blocked` 事件四处副作用原子发生；再触发 `reconcile_blocked` 验证解封推断。

**Acceptance Scenarios**:

1. **Given** 一个 active flow，**When** `BlockedStateService.set_block(branch, reason="Agent error")` 被调用，**Then** 同一事务内：`flow_state.blocked_reason` 写入、issue body 投影更新、task issue label → `state/blocked`、`flow_blocked` 事件写入 timeline。
2. **Given** 一个带 `blocked_reason` 的 blocked flow，**When** `reconcile_blocked(clear_reason=False)` 在 QualifyGate 中运行，**Then** 只要 `reason` 有值，`effective_blocked` 为真，系统**不**自动解封（手工阻塞信号阻止自动解封）。
3. **Given** 一个 blocked flow（无 reason，仅有未关闭的 `blocked_by_issue` 依赖），**When** 依赖 issue 全部 closed，**Then** `reconcile_blocked` 推断恢复（`infer_resume_label`），清除 body 阻塞段、重建缓存、回写 `flow_status`。

---

### User Story 3 - 依赖未满足阻塞（block by dependency）(Priority: P2)

flow 因依赖其他未关闭 issue 而阻塞，依赖关系由 issue body `Blocked by` 投影作为真源、`flow_issue_links(role='dependency')` 作为缓存。

**Why this priority**: 依赖链是跨 issue 编排的关键场景，但触发频度低于手工阻塞；其"真源 vs 缓存"分层是契约最容易漂移处。

**Independent Test**: 构造 `blocked_by_issue=N` + body `Blocked by` 段，运行 reconcile，观察 `flow_issue_links` 缓存从真源重建。

**Acceptance Scenarios**:

1. **Given** flow 的 issue body `Blocked by` 段列出 #A、#B，**When** reconcile 重建缓存，**Then** `flow_issue_links(role='dependency')` = {#A, #B}，`blocked_by_issue` 字段为主要依赖的快捷显示（非完整集合）。
2. **Given** 手工 `blocked_reason` 与依赖 `blocked_task` 同时存在，**When** 依赖全部关闭但 reason 未清，**Then** flow 仍判定 blocked（二者独立且可共存）。

---

### User Story 4 - 手动恢复（task resume）(Priority: P2)

用户通过 `vibe3 task resume` 主动清除 blocked 状态，恢复保留 flow 现场（不删 worktree/branch/record），按 flow refs 推断恢复 label。

**Why this priority**: 主动恢复是阻塞→活跃的唯一人工入口，契约需保证"只清状态、不毁现场"。

**Independent Test**: 对一个 blocked flow 执行 `task resume`，验证 `blocked_reason` 清除、label 推断恢复、worktree/branch/record 完好。

**Acceptance Scenarios**:

1. **Given** 一个 blocked flow 且 worktree 仍在，**When** `vibe3 task resume <issue>` 执行（默认 `--label auto`），**Then** blocked cache/body/label 清除，label 按 flow refs 推断恢复，worktree/branch/flow record **不**删除。
2. **Given** label-auto 恢复时发现 recorded worktree/ref 场景已丢失，**When** `task resume` 执行，**Then** 系统**委托 explicit rebuild path** 而非静默继续。

---

### User Story 5 - 显式重建（flow rebuild）(Priority: P3)

`vibe3 flow rebuild` 是唯一公共 destructive 重建入口：hard delete 旧 flow/worktree/branch，重新 bootstrap，append rebuild handoff event，再调用 label-auto resume 清除 blocked。

**Why this priority**: 重建是低频但高破坏性操作，契约需明确"显式意图 + hard delete + 不作常规恢复路径"。

**Independent Test**: 对一个 blocked flow 执行 `flow rebuild`，验证旧 scene 被 hard delete、新 scene bootstrap、handoff event append、blocked label 清除。

**Acceptance Scenarios**:

1. **Given** 一个 blocked 或现场损坏的 flow，**When** `vibe3 flow rebuild <issue>` 执行，**Then** 旧 worktree/branch/flow record 被 hard delete（非软删除），新 flow/worktree bootstrap，handoff append rebuild 事件，label-auto resume 清除 blocked。

---

### User Story 6 - 被动清理孤儿 flow（check --clean-branch）(Priority: P3)

`aborted`/`stale` 终端 flow 由 `vibe3 check --clean-branch` 统一回收，对 aborted 软删除并被动恢复 issue label 至 `state/ready`。

**Why this priority**: 被动清理保证系统无现场残留；label 恢复时序（先清 flow 再 resume issue，且每条路径只调一次）是契约约束。

**Independent Test**: 构造一个 aborted flow，执行 `check --clean-branch`，验证软删除设置 `deleted_at`、issue label → `state/ready`、`resume_issue()` 仅调用一次。

**Acceptance Scenarios**:

1. **Given** 一个 aborted flow，**When** `check --clean-branch` 处理，**Then** `cleanup_flow_scene(keep_flow_record=False)` 软删除（设 `deleted_at`），随后 `_resume_blocked_issue` 将 task issue label 恢复至 `state/ready`，`resume_issue()` 在此路径恰好调用一次。

---

### Edge Cases

- **遗留状态值迁移**：从存储加载时，`flow_status` 的 `idle→active`、`missing→stale`、`merged→done`、`waiting→active` 由 `field_validator` 自动迁移；`execution_status` 的 `completed→done`、`failed→crashed` 自动迁移。`IssueState.FAILED` 标签自动映射为 `state/blocked`。
- **代码与文档差异**：`FlowState.flow_status` 的 Literal 仍包含 `review` 与 `failed`（代码注释："failed is now a valid terminal state (with PRs)"），与 [flow-lifecycle-standard.md](../../../docs/standards/flow-lifecycle-standard.md) §2.1 声称"`failed` 已彻底移除"存在出入。本 spec 以代码为准：`failed` 是带 PR 场景下的合法终态。规范同步走文档维护流程。
- **多 flow 绑定保护**：同一 issue 绑定多个 active flow 时，仅当全部进入 `done` 才关闭 issue，防止单分支合并过早关闭跨分支工作。
- **aborted/stale 的 label 处理缺口**：`mark_flow_aborted()` 与 `mark_flow_stale()` 当前未在方法内显式管理 task issue label（aborted 由后续 `check` 被动恢复，stale 依赖 governance 重建 ready flow 时处理）。
- **软删除查询隔离**：所有普通查询自动过滤 `deleted_at IS NULL`；仅 `get_flow_state_include_deleted` 与 `get_deleted_flows` 查询已删除记录。
- **loop 防护**：`FlowState.transition_count` 字段用于状态循环防护，防止 transition 在blocked↔active 间无限震荡。

## Requirements *(mandatory)*

### Functional Requirements

> 下列 MUST/SHOULD 描述 flow-lifecycle 子系统**当前已实现**的行为不变式。每条可通过对现有代码或命令的测试复现。

- **FR-001**: 系统 MUST 维护两个正交状态维度：`FlowStatus`（`flow_state.flow_status`，描述 flow 执行状态）与 `IssueState`（GitHub `state/*` label，描述 issue 编排状态）。二者不得互相替代。
- **FR-002**: `FlowStatus` 取值集合 MUST 为 `{active, blocked, done, stale, review, failed, aborted}`，其中 `done`/`review`/`failed`/`aborted` 为终态（`failed` 为带 PR 场景的合法终态，与 standard 文档表述存在已记录差异）。
- **FR-003**: `IssueState` 状态机 MUST 由 `ALLOWED_TRANSITIONS`（`models/orchestration.py`）定义：`READY→CLAIMED→HANDOFF→IN_PROGRESS↔HANDOFF→REVIEW↔HANDOFF→MERGE_READY↔HANDOFF→DONE`，且任意非终态 → `BLOCKED`。`validate_transition(force=True)` 可绕过（用于被动清理）。
- **FR-004**: ERROR 系统（`error_log` + FailedGate，控制派发）与 BLOCK 系统（`flow_status=blocked` + `blocked_reason`，控制业务流暂停）MUST 正交：执行失败计入 error_log，**不**直接改变 flow 业务状态位；业务阻塞计入 `blocked_reason`。
- **FR-005**: `BlockedStateService.set_block(...)` MUST 原子执行四处副作用：SQLite 写 `blocked_reason`/`blocked_by_issue`、GitHub issue body 投影、task issue label → `state/blocked`、`flow_blocked` timeline 事件。
- **FR-006**: 阻塞判定 MUST 遵循 `effective_blocked = (blocked_reason 有值) OR (任一 dependency 未关闭)`；手工 `blocked_reason` 与依赖 `blocked_task` 相互独立、可共存。
- **FR-007**: QualifyGate MUST 通过 `reconcile_blocked(clear_reason=False)` 对账核统一判定阻塞（不单独运行独立阻塞校验），依据 GitHub issue body 真源推断解封。
- **FR-008**: 自动解封 MUST 仅在"无 `reason` 且全部依赖关闭"时发生，调用 `infer_resume_label` 推断目标 label、清除 body 阻塞段、重建本地缓存并回写 `flow_status`。
- **FR-009**: `mark_flow_aborted()` / `mark_flow_stale()` MUST 为终端/等待状态（事件类型 `flow_auto_aborted` / `flow_auto_staled`）；二者当前未显式管理 task issue label（已知实现缺口，由 `check` 被动清理或 governance 重建处理）。
- **FR-010**: 多 flow 绑定同一 issue 时，issue 关闭 MUST 等待全部绑定 flow 进入 `done`；`close_issue_if_open` 返回 `closed`/`already_closed`/`failed` 且重复调用无副作用（幂等）。
- **FR-011**: 资源回收 MUST 通过 `vibe3 check --clean-branch` 统一入口，`FlowCleanupService.cleanup_flow_scene` 只清理物理资源（tmux/worktree/branch/handoff）**不**处理 issue label；issue label 恢复由调用者（`check` 或 `task resume`）协调，每条路径只调用一次 `resume_issue()`。
- **FR-012**: 默认清理 MUST 使用软删除（设 `deleted_at` ISO 8601 时间戳）；硬删除（`force=True`）仅在显式指定、测试清理或合规场景使用。`done` 记录保留（`deleted_at=NULL`），`aborted` 记录软删除。
- **FR-013**: 普通查询 MUST 自动过滤 `deleted_at IS NULL`；恢复软删除记录通过 `restore_flow()`（内部 API，CLI 已废弃）；创建新 flow 自动清除 `deleted_at`。
- **FR-014**: `vibe3 task resume` MUST 仅清除 blocked cache/body/label 并按 refs 推断 label，**不**删除 worktree/branch/flow record；现场已丢失时 MUST 委托 explicit rebuild path 而非静默继续。
- **FR-015**: `vibe3 flow rebuild` MUST 是唯一公共 destructive 重建入口：hard delete + re-bootstrap + append rebuild handoff event + label-auto resume；不作常规恢复路径。
- **FR-016**: 每次状态变化 MUST 通过 timeline 记录事件（`flow_blocked`/`resumed`/`done`/`aborted`/`deleted`/`restored` 等），含 actor 与 detail。
- **FR-017**: `AbandonFlowService` 当前为 dead code candidate（公开导出但无外部引用，见 [services/flow/README.md](../../../src/vibe3/services/flow/README.md)）；baseline 保留其导出但标记待 follow-up 验证。

### Key Entities *(include if feature involves data)*

> 字段语义权威真源为 [models/flow.py](../../../src/vibe3/models/flow.py) 与 [docs/standards/v3/data-model-standard.md](../../../docs/standards/v3/data-model-standard.md)。此处仅列契约层面的实体，不复述全字段。

- **FlowState**：flow 的核心持久化状态（`branch` 为主键、`flow_status` 状态维度、`blocked_reason`/`blocked_by_issue` 阻塞信号、`*_ref` 各阶段产物引用、`deleted_at` 软删除戳、`transition_count` 循环防护计数、`worktree_path`/`creation_source` 现场锚点）。Session 跟踪已迁移至 runtime_session registry，旧 `*_session_id` 字段已从模型移除。
- **IssueLink**：flow↔issue 的角色化关联（`role ∈ {task, related, dependency}`）。`task` role 是关闭真源；`dependency` role 是依赖缓存（真源为 body `Blocked by`）。
- **FlowEvent**：timeline 事件记录（`event_type`/`actor`/`detail`/`refs`），`refs` 在加载时被 `normalize_refs` 强制字符串化以兼容历史数据。
- **BlockedState**：阻塞状态的领域封装（`BlockedStateService` 统一管理，提供 `set_block`/`clear_block`/`reconcile_blocked`/`is_blocked`）。
- **IssueState**（label 维度）：`READY`/`CLAIMED`/`IN_PROGRESS`/`BLOCKED`/`HANDOFF`/`REVIEW`/`MERGE_READY`/`DONE`，状态机见 FR-003。

## Success Criteria *(mandatory)*

### Measurable Outcomes

> baseline 语境下，"成功标准"指**系统当前已满足且可回归验证**的契约属性。

- **SC-001**: 所有 `FlowStatus` 状态转换均可通过现有单元测试覆盖（正常完成、阻塞后恢复、阻塞后重建、被动清理、依赖阻塞自动恢复、FailedGate 清理无效 FAILED label、软删除/硬删除/恢复）。
- **SC-002**: `BlockedStateService.set_block` 的四处原子副作用在事务性测试中要么全部成功、要么全部不生效（无中间状态）。
- **SC-003**: 多 flow 绑定同一 issue 的关闭保护在集成测试中可验证（单分支 merge 不关闭跨分支 issue）。
- **SC-004**: 软删除记录在所有普通查询中被过滤，仅在显式 include-deleted 查询中可见。
- **SC-005**: ERROR 系统与 BLOCK 系统正交：向 `error_log` 记录错误**不**改变 `flow_status` 业务状态位（可通过对 `record_error` 后 `flow_status` 未变的测试验证）。
- **SC-006**: 遗留状态值（`idle`/`missing`/`merged`/`waiting`/`completed`/`failed`(execution)）在从存储加载时被自动迁移，不产生加载失败。

## Assumptions

- **baseline 范围假设**：本 spec 覆盖 `services/flow/*` 与 flow 状态机、阻塞服务、清理/恢复/重建、PR 生命周期交互。**不**覆盖 dispatch 协调器内部（见 002-dispatch-execution）、role 触发协议（见 003-role-protocol）、environment/worktree 物理管理（见 004-environment-isolation）。
- **真源分层假设**：GitHub issue body 托管投影（`State`/`Blocked reason`/`Blocked by`）为真源，SQLite `flow_state` + `flow_issue_links` 为缓存，`state/*` label 为信号，git branch/worktree 为物理现场载体（非真源系统成员）。
- **写入权边界假设**：orchestra 不直接写 `flow_state`；manager 不直接改 issue label（经 LabelService）；check 不参与业务判断；这些边界由 [flow-lifecycle-standard.md](../../../docs/standards/flow-lifecycle-standard.md) §1-2 定义，本 spec 引用不复述。
- **与 standard 的偏差假设**：`failed` 作为带 PR 合法终态、`AbandonFlowService` dead code、aborted/stale 未显式管理 label，均为 baseline 已知差异；其修正属于后续演进，不在本 spec 范围。
