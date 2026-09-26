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

`BlockedStateService.set_block()` reads the issue body, writes a blocked projection, then calls `sync_block_state()`. Synchronization reads the remote projection, resolves dependencies, and aligns the local flow/dependency cache and blocked label. It does not resume a flow.

These operations are sequential cross-system writes. They are **not** one database transaction and the implementation does not guarantee all-or-nothing atomicity across GitHub, SQLite, labels, and timeline events. The issue body/label path is treated as authoritative; local data is repairable cache.

### Scenario 3 - Manual and automatic recovery have separate authority

Explicit manual resume may clear a human blocked reason after checking remote truth and dependencies. Automatic recovery first evaluates read-only eligibility, then applies a decision bound to the issue snapshot. Existing flows resume to `handoff`; pre-flow issues resume to `ready`. Rebuild repairs the physical scene without clearing a human reason or inferring a business target from refs.

### Scenario 4 - Terminal state and resource cleanup

Flow completion and scene cleanup are separate. Cleanup may remove tmux/worktree/branch/handoff resources while preserving or soft-deleting the flow record according to the caller. Ordinary queries exclude soft-deleted rows. Multi-flow issue closure waits for the relevant bound flows rather than treating one branch as the entire issue.

## Requirements

- **FR-001**: `FlowState.flow_status` MUST accept the values implemented in `models/flow.py`: `active`, `blocked`, `done`, `stale`, `review`, `failed`, and `aborted`.
- **FR-002**: GitHub `IssueState` transitions MUST be validated by `ALLOWED_TRANSITIONS` unless a caller explicitly uses the force path.
- **FR-003**: error severity / FailedGate state MUST remain separate from business blocked state; recording an execution error does not by itself set `flow_status=blocked`.
- **FR-004**: `set_block()` MUST write remote body truth before invoking blocked-state synchronization. It MUST NOT be described as an atomic four-system transaction.
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
| [#3293](https://github.com/jacobcy/vibe-coding-control-center/pull/3293) | Separated manual resume authority from snapshot-bound automatic eligibility. |

## Known gaps and tracking

| Gap | Current evidence | Tracking |
|---|---|---|
| Manual resume still exposes a `force=True` dependency override, although the original issue deferred that capability. | The override exists only on the manual API; its acceptance boundary remains open. | [#3289](https://github.com/jacobcy/vibe-coding-control-center/issues/3289) |
| Multi-dependency truth is richer than the legacy single `blocked_by_issue` column. | Body projection and dependency links support multiple issues; the column stores one. | [#3248](https://github.com/jacobcy/vibe-coding-control-center/issues/3248) |
| Periodic PR-terminal reconciliation does not cover every aborted-flow recovery case. | Existing check path has an open lifecycle follow-up. | [#3227](https://github.com/jacobcy/vibe-coding-control-center/issues/3227) |
| `AbandonFlowService` has tests but no production consumer. | Repository search finds only its module, README, and tests. Desired removal is unambiguous after compatibility confirmation. | [#3303](https://github.com/jacobcy/vibe-coding-control-center/issues/3303) |

## Success Criteria

- The baseline never claims cross-system atomicity that the implementation does not provide.
- Current manual and automatic recovery authority is described from the merged implementation.
- Every known implementation gap is linked to an open issue or explicitly routed for follow-up.

## Non-goals

- Changing the manual/automatic resume API.
- Implementing normalized dependency storage.
- Changing flow lifecycle code as part of this archive correction.

## spec 012 touchpoints

Spec 012 (Spec Artifact Handoff Bridge) delivered by #3310-#3313:
- consistency now covers spec_ref/plan_ref/report_ref/audit_ref through one shared resolution contract (FR-010)
- missing-artifact classification distinguishes repair blockers from physical scene rebuild (FR-011)
