# Feature Specification: Environment Isolation Baseline

**Feature Branch**: `dev/issue-3299`

**Created**: 2026-07-03

**Status**: Draft (Baseline / Reverse Specification)

**Spec Mode**: 逆向规格化（Reverse Specification）。本 spec 描述 environment 隔离子系统**当前代码的行为契约**，作为后续变更的行为参照基线。**不设计新功能、不改代码。**

**Input**: User description: "逆向规格化 environment-isolation 模块的现有行为契约（baseline spec，非新功能设计）"

## Spec Mode 说明

本 spec 是 **baseline 行为契约**，描述"系统现在如何用 worktree + session 隔离执行环境"。代码真源：

- `src/vibe3/environment/*`（worktree / worktree_lifecycle / worktree_support / worktree_pr_mixin / worktree_context / session / session_registry / session_naming）
- `runtime_session` 表（session 持久化）

**冲突处理**：当代码现状与文档不一致时，本 spec 以代码行为为准并显式标注。**范围边界**：本 spec 不承载项目硬规则，仅引用 [CLAUDE.md](../../../CLAUDE.md) §HARD RULES（#8 Agent 与 worktree 一对一）、[.claude/rules/modularity-standards.md](../../../.claude/rules/modularity-standards.md)、[.specify/memory/constitution.md](../../memory/constitution.md) 原则 V（Worktree-Isolated Specs）。

**关联 spec**：与 [002-dispatch-execution](../002-dispatch-execution/spec.md) 协作——execution 通过 environment 分配 worktree/session；与 [001-flow-lifecycle](../001-flow-lifecycle/spec.md) 协作——flow 的 `worktree_path` 字段锚定现场。

**Constitution 原则 V 强制**：路径解析相关条款 MUST 兼容 bare-repo + linked-worktree 模型（本 spec 核心约束）。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - L3 Issue Worktree 长期任务隔离 (Priority: P1)

绑定 issue 的长期任务（manager/plan/run/review）在 L3 issue worktree 中执行：路径 `{worktree_root}/issue-{number}-{hash}/`，生命周期与 issue 一致，issue 重新激活时可复用已有 worktree。

**Why this priority**: L3 是核心开发任务的物理隔离基础，支持跨 session 持久化与现场恢复，是 HARD RULES #8（Agent 与 worktree 一对一）的物理实现。

**Independent Test**: 对 issue #N 调用 `acquire_issue_worktree`，验证路径形如 `issue-N-{hash}/`；再次 acquire（复用场景）验证返回已存在的同一路径。

**Acceptance Scenarios**:

1. **Given** issue #123 首次激活，**When** `WorktreeManager.acquire_issue_worktree(...)` 调用，**Then** 创建路径 `{worktree_root}/issue-123-{hash}/` 的 worktree，并经 `FlowStatePort.update_flow_metadata()` 记录到 `flow_state.worktree_path`。
2. **Given** issue #123 的 L3 worktree 已存在，**When** issue 重新激活后再次 acquire，**Then** 复用已有 worktree（不重复创建），返回同一路径。
3. **Given** 一个使用中的 L3 worktree，**When** `release_issue_worktree` 调用，**Then** 可选回收（默认保留供恢复，不强制清理）。

---

### User Story 2 - L2 Temporary Worktree 短期任务隔离 (Priority: P1)

governance 扫描、supervisor 检查等短期任务在 L2 temporary worktree 中执行：路径 `{worktree_root}/temp-{hash}/`，任务完成后强制回收，不支持复用。

**Why this priority**: L2 保证短期任务用完即清，避免与 L3 长期现场混淆，是 governance/supervisor 同步执行的资源基础。

**Independent Test**: 调用 `acquire_temporary_worktree`，验证路径形如 `temp-{hash}/`；任务后 `release_temporary_worktree` 验证强制清理（`git worktree remove --force` + `shutil.rmtree()`）。

**Acceptance Scenarios**:

1. **Given** governance 扫描任务，**When** `acquire_temporary_worktree(...)` 调用，**Then** 创建路径 `{worktree_root}/temp-{hash}/` 的临时 worktree。
2. **Given** 一个 L2 temporary worktree，**When** `release_temporary_worktree` 调用，**Then** 强制清理（不复用、不保留）。
3. **Given** L2 vs L3 选择，**When** 任务类型为 issue-bound 长期开发，**Then** 走 L3；当任务类型为 governance/supervisor 短期，**Then** 走 L2。

---

### User Story 3 - Bare Repo + Linked Worktree 兼容 (Priority: P1)

本项目仓库根是 bare repository（无 working tree），实际工作发生在 linked worktrees（`.git` 为 gitdir pointer）。environment 层所有路径解析 MUST 从 worktree 自身解析，不得假设仓库根有 working tree。

**Why this priority**: 这是 constitution 原则 V 的硬约束（依据 PR #3268 #3253 #3246 bare repo compatibility、#3259 #3277 path anchoring）；违反将导致路径解析在 bare repo 下系统性失败。

**Independent Test**: 在 bare repo 的 linked worktree 中运行路径解析（如定位 `scripts/init.sh`），验证从 worktree 路径解析而非仓库根。

**Acceptance Scenarios**:

1. **Given** 本项目仓库根为 bare repo（无 working tree），**When** environment 层解析资源路径（如 `scripts/init.sh`），**Then** 从当前 worktree 路径解析，**不**从仓库根解析（仓库根无 working tree，会失败）。
2. **Given** linked worktree（`.git` 为 gitdir pointer），**When** worktree 生命周期操作（创建/验证/回收），**Then** 正确处理 gitdir pointer 语义（`worktree_lifecycle.py:303` 明确支持 linked worktrees）。
3. **Given** 任意 spec 条款涉及路径解析，**When** 实现该条款，**Then** MUST 兼容 bare-repo + linked-worktree 模型（constitution 原则 V）。

---

### User Story 4 - Session 生命周期与注册表 (Priority: P2)

每个执行 session 经 `SessionRegistryService` 注册：`reserve(starting) → mark_started(running) → mark_finished(done|failed) / mark_aborted / mark_failed`，持久化到 `runtime_session` 表（15 列）。

**Why this priority**: session 注册表是并发安全与容量控制的真源（`count_live_*_sessions` 驱动 dispatch 容量，见 002 FR-003）。

**Independent Test**: 创建一个 session 经完整生命周期，验证 `runtime_session` 表状态转换与 `count_live_worker_sessions` 计数变化。

**Acceptance Scenarios**:

1. **Given** 一个新 session，**When** `reserve(...)` 调用，**Then** `runtime_session` 写入一条 `status="starting"` 记录（session_name、worktree_path、target_type、target_id、branch 等）。
2. **Given** 一个 starting session，**When** tmux 启动后 `mark_started(...)` 调用，**Then** `status` → `"running"`、`started_at` 写入。
3. **Given** 一个 running session，**When** `mark_finished(success=True/False)` 调用，**Then** `status` → `"done"` 或 `"failed"`。
4. **Given** 用户主动终止，**When** `mark_aborted(...)` 调用，**Then** `status` → `"aborted"`、`ended_at` 写入。
5. **Given** 多个 session 查询，**When** `count_live_worker_sessions(role=...)` 调用，**Then** 返回当前 live worker session 数（驱动容量，见 002 FR-003）。

---

### User Story 5 - Session 命名规则 (Priority: P3)

session 命名遵循 `vibe3-{role}-{target_type}-{target_id}` 格式（如 `vibe3-manager-issue-123`、`vibe3-plan-issue-456`），语义化标识符用连字符分隔。

**Why this priority**: 命名规则是 session 可读性与查询的基础，保证 session_name 全局唯一且语义自解释。

**Independent Test**: 对 manager/plan/run/review 各角色生成 session 名，验证格式一致。

**Acceptance Scenarios**:

1. **Given** manager 角色针对 issue #123，**When** 生成 session 名，**Then** 为 `vibe3-manager-issue-123`。
2. **Given** plan 角色针对 issue #456，**When** 生成 session 名，**Then** 为 `vibe3-plan-issue-456`。

---

### User Story 6 - 并发安全与孤儿清理 (Priority: P3)

session 注册表确保同一 worktree 不被多个 session 并发占用；`reconcile_live_state` 与 `mark_*_done_when_tmux_gone` 清理 tmux 已消失但注册表仍 live 的孤儿 session。

**Why this priority**: 并发安全防止 worktree 竞态；孤儿清理防止注册表与 tmux 现实漂移导致容量计数虚高。

**Independent Test**: 构造 tmux 已死但注册表仍 running 的 session，调用 `mark_worker_sessions_done_when_tmux_gone`，验证状态被纠正。

**Acceptance Scenarios**:

1. **Given** worktree W 已被 session A 占用，**When** session B 尝试占用 W，**Then** 被注册表拒绝（并发安全）。
2. **Given** session 的 tmux 已消失但 `runtime_session.status="running"`，**When** `mark_worker_sessions_done_when_tmux_gone()` 或 `mark_governance_sessions_done_when_tmux_gone()` 调用，**Then** 孤儿 session 被标记 done，`count_live_*` 计数下降。
3. **Given** 注册表与 tmux 现实可能漂移，**When** `reconcile_live_state()` 周期调用，**Then** 校正注册表与实际 tmux 状态一致。

---

### Edge Cases

- **前置 prune**：worktree 创建前 `git worktree prune` 清理 stale references，避免残留指向干扰新 worktree 创建。
- **L2 强制 vs L3 可选回收**：`release_temporary_worktree` 强制 `git worktree remove --force` + `shutil.rmtree()`；`release_issue_worktree` 默认可选回收（保留供恢复）。
- **session 日志保留**：session 销毁后 log（`.git/vibe3/logs/{session_name}.log`）保留供事后排查。
- **keep_alive 与异步执行**：`TmuxSessionContext.keep_alive_seconds` 控制异步 session 保活；超 keep_alive 的 session 由注册表自动清理。
- **auto-scene 对齐**：`align_auto_scene_to_base(cwd, flow_branch)` 支持将 auto-scene 对齐到 base 分支；`resolve_manager_cwd` 解析 manager 执行 cwd。
- **bootstrap 资源解析边界**：`resolve_bootstrap_worktree_context()` 只提供资源描述（WorktreeContext），**不**执行 issue intake、flow bind、snapshot 等业务逻辑，**不**编排 workflow（编排属 Skill 层）。
- **L1 未显式定义**：environment 中显式分层为 L2（temporary）/ L3（issue-bound）；"L1"未在 environment 模块显式出现（可能指主仓库根的 bare repo 本身，但代码无此命名）。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系统 MUST 提供两层 worktree 隔离：L3 issue worktree（绑定 issue、路径 `issue-{number}-{hash}/`、支持复用、默认可选回收）与 L2 temporary worktree（无绑定、路径 `temp-{hash}/`、不复用、强制回收）。
- **FR-002**: `WorktreeManager.acquire_issue_worktree(...)` MUST 在 issue 首次激活时创建 L3 worktree，重复激活时复用已存在 worktree；并通过 `FlowStatePort.update_flow_metadata()` 将路径记录到 `flow_state.worktree_path`。
- **FR-003**: `WorktreeManager.acquire_temporary_worktree(...)` MUST 每次创建新 L2 worktree（不复用）；`release_temporary_worktree(...)` MUST 强制清理（`git worktree remove --force` + `shutil.rmtree()`）。
- **FR-004**: 所有 worktree 路径解析 MUST 从 worktree 自身解析，**不**假设仓库根有 working tree（本项目仓库根为 bare repo，依据 PR #3268 #3253 #3246）。
- **FR-005**: worktree 生命周期操作 MUST 兼容 linked-worktree 模型（`.git` 为 gitdir pointer），由 `worktree_lifecycle.py` 明确支持。
- **FR-006**: worktree 创建前 MUST 执行 `git worktree prune` 清理 stale references。
- **FR-007**: `SessionRegistryService` MUST 维护 session 生命周期：`reserve(starting) → mark_started(running) → mark_finished(done|failed) / mark_aborted / mark_failed`，持久化到 `runtime_session` 表（15 列）。
- **FR-008**: session 命名 MUST 遵循 `vibe3-{role}-{target_type}-{target_id}` 格式（连字符分隔、语义化、全局唯一）。
- **FR-009**: `SessionRegistryService.count_live_worker_sessions(role=...)` 与 `count_live_governance_sessions()` MUST 返回当前 live session 数，作为 dispatch 容量控制真源（见 002 FR-003）。
- **FR-010**: session 注册表 MUST 保证并发安全：同一 worktree 不被多个 session 同时占用。
- **FR-011**: `SessionRegistryService` MUST 提供 tmux 现实校正：`mark_worker_sessions_done_when_tmux_gone()` / `mark_governance_sessions_done_when_tmux_gone()` / `reconcile_live_state()` 清理 tmux 已消失但注册表仍 live 的孤儿 session。
- **FR-012**: session 销毁后其日志（`.git/vibe3/logs/{session_name}.log`）MUST 保留供事后排查（不随 session 销毁删除）。
- **FR-013**: `WorktreeManager.resolve_bootstrap_worktree_context()` MUST 只提供资源描述（WorktreeContext），**不**执行 issue intake/flow bind/snapshot 等业务逻辑，**不**编排 workflow（编排属 Skill 层，HARD RULES #16 Skill-First）。
- **FR-014**: `align_auto_scene_to_base(cwd, flow_branch)` MUST 支持将 auto-scene 对齐到 base 分支；`resolve_manager_cwd` MUST 解析 manager 执行 cwd（处理 bare repo 下的 cwd 解析）。

### Key Entities *(include if feature involves data)*

- **WorktreeContext**：worktree 描述（路径、分支、issue），是不可变资源描述。
- **WorktreeManager**：worktree 管理主入口（`WorktreePRMixin` 子类），提供 L2/L3 acquire/release。
- **WorktreeLifecycle**：worktree 生命周期编排（创建/验证/回收），支持 bare repo + linked worktree。
- **SessionRegistryService**：session 注册表，持久化 `runtime_session` 表，维护 session↔worktree↔tmux 映射。
- **runtime_session 表**：15 列（id、session_name、role、target_type、target_id、branch、status、worktree_path、tmux_session、log_path、started_at、ended_at、created_at、updated_at、backend_session_id）。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: L3 issue worktree 对同一 issue 重复 acquire 返回相同路径（复用可测试）；L2 temporary worktree 每次返回新路径且 release 后强制清理（可测试）。
- **SC-002**: 在 bare repo（仓库根无 working tree）环境下，environment 层所有路径解析从 worktree 自身成功解析，不从仓库根解析（可构造 bare repo 测试验证，依据 PR #3268 #3253 #3246）。
- **SC-003**: session 生命周期五态（starting/running/done/failed/aborted）在 `runtime_session.status` 上可观测，且 `count_live_*` 计数随状态变化正确增减。
- **SC-004**: 构造 tmux 已消失但注册表 running 的孤儿 session，`mark_*_done_when_tmux_gone` 调用后状态被纠正为 done、live 计数下降。
- **SC-005**: 同一 worktree 被并发 session 占用时，注册表拒绝第二个 session（并发安全可测试）。
- **SC-006**: `resolve_bootstrap_worktree_context()` 不触发 issue intake/flow bind/snapshot 等业务副作用（边界可测试，符合 HARD RULES #16）。

## Assumptions

- **baseline 范围假设**：本 spec 覆盖 worktree（L2/L3）生命周期、bare repo + linked worktree 兼容、session 生命周期与注册表、命名规则、并发安全、孤儿清理、bootstrap 资源解析边界。**不**覆盖 dispatch 如何调用 environment（见 002）、flow 状态语义（见 001）、tmux 内部实现细节。
- **bare repo 假设**：本项目仓库根为 bare repo（无 working tree），所有开发发生在 linked worktrees；此为 constitution 原则 V 的硬约束背景。
- **L1 假设**：environment 显式分层为 L2/L3；"L1"未在代码显式出现，本 spec 不臆测其定义。
- **HARD RULES #8 假设**：Agent 与 worktree 一对一，agent 只操作当前 worktree，不跨 worktree 切换；environment 层为此提供物理隔离基础，但该规则的治理真源在 [CLAUDE.md](../../../CLAUDE.md) §HARD RULES #8，本 spec 引用不复述。
- **Skill-First 边界假设**：bootstrap 资源解析只提供物理描述，编排（workflow 选择、issue intake）属 Skill 层，environment 不越权（HARD RULES #16）。
