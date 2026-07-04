# Feature Specification: Flow Lifecycle Baseline

**Feature Branch**: `dev/issue-3299`
**Created**: 2026-07-03
**Corrected**: 2026-07-04
**Status**: Baseline / Reverse Specification

## Purpose and truth sources

This specification records the behavior currently implemented by:

- `src/vibe3/models/flow.py`
- `src/vibe3/models/orchestration.py`
- `src/vibe3/services/flow/`
- the flow, blocked-state, cleanup, recovery, and lifecycle tests under `tests/vibe3/`

It is not a proposal. When a desired contract differs from current code, the difference is listed under **Known gaps and tracking** rather than written as an implemented requirement.

## User Scenarios & Testing

### Scenario 1 - Flow and issue state remain separate

A flow stores its execution lifecycle in `flow_state.flow_status`. GitHub `state/*` labels represent orchestration state. Code may project or reconcile between them, but they are not the same field and neither is a complete replacement for the other.

### Scenario 2 - Remote-first blocked-state reconciliation

`BlockedStateService.set_block()` reads the issue body, writes a blocked projection, then calls `reconcile_blocked()`. Reconciliation reads the remote projection, resolves dependencies, updates the local flow/dependency cache, converges the state label, and records a transition when possible.

These operations are sequential cross-system writes. They are **not** one database transaction and the implementation does not guarantee all-or-nothing atomicity across GitHub, SQLite, labels, and timeline events. The issue body/label path is treated as authoritative; local data is repairable cache.

### Scenario 3 - Manual and automatic recovery use the current shared path

The current implementation still exposes `reconcile_blocked(clear_reason=...)` and uses ref-based `infer_resume_label()`. Manual resume and system recovery therefore share permission-bearing primitives. This is current behavior, not the desired contract; #3289 tracks their separation.

### Scenario 4 - Terminal state and resource cleanup

Flow completion and scene cleanup are separate. Cleanup may remove tmux/worktree/branch/handoff resources while preserving or soft-deleting the flow record according to the caller. Ordinary queries exclude soft-deleted rows. Multi-flow issue closure waits for the relevant bound flows rather than treating one branch as the entire issue.

## Requirements

- **FR-001**: `FlowState.flow_status` MUST accept the values implemented in `models/flow.py`: `active`, `blocked`, `done`, `stale`, `review`, `failed`, and `aborted`.
- **FR-002**: GitHub `IssueState` transitions MUST be validated by `ALLOWED_TRANSITIONS` unless a caller explicitly uses the force path.
- **FR-003**: error severity / FailedGate state MUST remain separate from business blocked state; recording an execution error does not by itself set `flow_status=blocked`.
- **FR-004**: `set_block()` MUST write remote body truth before invoking reconciliation. It MUST NOT be described as an atomic four-system transaction.
- **FR-005**: blocked reconciliation MUST fail closed when remote truth cannot be read and MUST treat a non-empty human reason or any unresolved dependency as blocked.
- **FR-006**: dependency links in `flow_issue_links(role='dependency')` MUST be treated as local cache derived from the issue projection. The legacy `blocked_by_issue` field remains a single-value compatibility pointer.
- **FR-007**: normal flow queries MUST exclude rows with `deleted_at`; include-deleted APIs are explicit.
- **FR-008**: cleanup MUST check live-session ownership before removing physical resources and MUST leave issue-label decisions to the coordinating caller.
- **FR-009**: timeline/event writes are best-effort observability around state changes; their presence does not make GitHub and SQLite writes transactional.
- **FR-010**: `AbandonFlowService` is an internal, tested class with no production consumer and is not part of the flow package public barrel.

## Key implementation PRs

| PR | Contribution |
|---|---|
| [#3247](https://github.com/jacobcy/vibe-coding-control-center/pull/3247) | Unified blocked-state write/reconcile primitives and dependency convergence. |
| [#3201](https://github.com/jacobcy/vibe-coding-control-center/pull/3201) | Expanded flow-status consumers for `review`, `failed`, and `aborted`. |
| [#3282](https://github.com/jacobcy/vibe-coding-control-center/pull/3282) | Corrected dispatch waiting/live-session behavior that consumes flow state. |

## Known gaps and tracking

| Gap | Current evidence | Tracking |
|---|---|---|
| Manual resume authority and automatic recovery eligibility share mutable primitives and ref-based target inference. | `reconcile_blocked(clear_reason=...)` and `infer_resume_label()` remain callable by recovery paths. | [#3289](https://github.com/jacobcy/vibe-coding-control-center/issues/3289) |
| Multi-dependency truth is richer than the legacy single `blocked_by_issue` column. | Body projection and dependency links support multiple issues; the column stores one. | [#3248](https://github.com/jacobcy/vibe-coding-control-center/issues/3248) |
| Periodic PR-terminal reconciliation does not cover every aborted-flow recovery case. | Existing check path has an open lifecycle follow-up. | [#3227](https://github.com/jacobcy/vibe-coding-control-center/issues/3227) |
| `AbandonFlowService` has tests but no production consumer. | Repository search finds only its module, README, and tests. Desired removal is unambiguous after compatibility confirmation. | [#3303](https://github.com/jacobcy/vibe-coding-control-center/issues/3303) |

## Success Criteria

- The baseline never claims cross-system atomicity that the implementation does not provide.
- Current recovery behavior and the intended #3289 replacement are visibly separated.
- Every known implementation gap is linked to an open issue or explicitly routed for follow-up.

## Non-goals

- Defining the future manual/automatic resume API.
- Implementing normalized dependency storage.
- Changing flow lifecycle code as part of this archive correction.
