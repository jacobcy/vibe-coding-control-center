# Feature Specification: Dispatch Execution Baseline

**Feature Branch**: `dev/issue-3299`
**Created**: 2026-07-03
**Corrected**: 2026-07-04
**Status**: Baseline / Reverse Specification

## Purpose and truth sources

Current behavior is defined by `src/vibe3/domain/dispatch_*`, `src/vibe3/domain/handlers/`, `src/vibe3/execution/`, and their tests. This baseline separates queue/dispatch decisions, execution lifecycle, monitoring views, and post-execution gates.

## User Scenarios & Testing

### Scenario 1 - Intent to execution request

Label-driven domain intents are handled and enriched into `ExecutionRequest` values. Preflight/qualify checks and capacity checks decide whether a request may launch. The coordinator and handlers preserve issue, branch, role, source, and tick context for error tracking.

### Scenario 2 - Execution lifecycle and session observation

Execution start/completion persistence belongs to actor and execution-lifecycle components. `JobMonitorService` does not own `record_start`, `record_completion`, or `get_active_jobs` mutations; it builds a read-only snapshot from `ActorRegistry` plus optional durable `runtime_session` rows.

### Scenario 3 - Post-execution no-op enforcement

`apply_unified_noop_gate()` runs after the agent returns. It validates required refs/verdicts and whether the managed state-label set changed. Missing required output or an unchanged state can invoke the role-specific block function. It is not the first step of `dispatch_execution()`.

### Scenario 4 - Dependency closure notification

PR #3286 introduced `IssueResolvedDependency`, dependent lookup, and an advisory `DependencyClosureGate` notification path. The current branch does not contain the observer-only mutation/re-evaluation service described by #3292.

## Requirements

- **FR-001**: dispatch collection MUST re-run qualify gates and capacity checks before launch rather than assuming queued entries remain eligible.
- **FR-002**: sleep/paused lifecycle state MUST throttle collection according to the dispatch lifecycle FSM.
- **FR-003**: execution lifecycle MUST record durable runtime-session state through its lifecycle/registry collaborators; monitoring MUST remain a derived view.
- **FR-004**: `JobMonitorService.snapshot()` MUST merge active/recent actor data with available runtime-session rows and tolerate store read failures by returning the actor-derived view.
- **FR-005**: the no-op gate MUST run after agent completion and MUST validate the role's declarative output contract.
- **FR-006**: reviewer execution MUST produce `latest_verdict`; planner execution MUST produce `plan_ref`; executor has no unconditional required ref in `RoleOutputContract`.
- **FR-007**: FailedGate MUST be driven by persisted error severity/count thresholds, not reviewer verdict values or business `state/blocked` labels.
- **FR-008**: dependency closure notification MUST remain advisory in the current baseline; it MUST NOT be described as automatically resuming a dependent flow.

## Key implementation PRs

| PR | Contribution |
|---|---|
| [#3286](https://github.com/jacobcy/vibe-coding-control-center/pull/3286) | Added the dependency-resolution event model, dependent lookup, and advisory closure gate. |
| [#3282](https://github.com/jacobcy/vibe-coding-control-center/pull/3282) | Fixed waiting-state and live-session checks that caused duplicate dispatch. |
| [#3252](https://github.com/jacobcy/vibe-coding-control-center/pull/3252) | Supplied flow context to the post-execution no-op gate. |
| [#3234](https://github.com/jacobcy/vibe-coding-control-center/pull/3234) | Unified collection interval behavior and corrected gate ordering. |
| [#3232](https://github.com/jacobcy/vibe-coding-control-center/pull/3232) | Added sleep-mode collection throttling through the dispatch lifecycle FSM. |

## Known gaps and tracking

| Gap | Coverage |
|---|---|
| Dependency closure needs an observer-only evaluator/apply path that cannot clear a human reason or infer an unsafe target. | [#3292](https://github.com/jacobcy/vibe-coding-control-center/issues/3292), dependent on [#3289](https://github.com/jacobcy/vibe-coding-control-center/issues/3289). |
| Qualify-gate exceptions are being migrated to the shared hybrid error classifier. | [#3272](https://github.com/jacobcy/vibe-coding-control-center/issues/3272). |

## Success Criteria

- Monitoring APIs are not confused with execution mutation APIs.
- Advisory dependency notification is not described as delivered auto-resume.
- FailedGate, no-op gate, and business blocked state remain distinct mechanisms.

## Non-goals

- Implementing #3292.
- Redesigning dispatch capacity or lifecycle state.
- Changing runtime code in this archive pass.
