---
document_type: design
title: Dispatch and No-Op Invariants Repair
status: proposed
scope: Issue 3281 dispatch idempotency, no-op boundary, blocked recovery, and transition loop protection
author: Codex
created: 2026-07-01
last_updated: 2026-07-01
related_docs:
  - docs/standards/v3/noop-gate-boundary-standard.md
  - docs/standards/v3/blocked-dependency-reconciliation-standard.md
  - docs/standards/flow-lifecycle-standard.md
  - docs/decisions/0004-domain-flow-event-boundary.md
---

# Dispatch and No-Op Invariants Repair Design

## Goal

Restore the business boundary broken by recent dispatch and blocked-state
convergence work without returning to the former patch stack.

The repair keeps unified mechanisms where they reduce duplication: remote I/O,
session liveness, blocked truth reconciliation, and transition accounting. It
removes unified business decisions from dispatch and execution infrastructure.
Normal state progression remains owned by the agent or human operating the
flow.

## Authoritative Invariants

### Normal dispatch does not infer progress

For every non-blocked issue, dispatch uses the current authoritative GitHub
state label as its role trigger. Dispatch may verify queue eligibility, remote
intervention, capacity, session liveness, and worktree health. It must not use
flow refs, verdicts, reports, plans, PR cache, or inferred completion to choose a
different state.

`DispatchPreflightDecision.target_state` for an active issue is therefore the
observed issue state or no decision. It is never an inferred next state.

### A waiting queue entry is an in-flight lease

After emitting a dispatch intent, the queue entry's `waiting_state` records the
state for which that intent was emitted. While the authoritative issue state is
unchanged, the coordinator must not emit another intent for that entry.

The coordinator may still reload a waiting issue to detect removal conditions:
closure, explicit blocked state, disallowed assignee, supervisor ownership, or
other queue-exclusion labels. Observation and invalidation must not make the
entry dispatchable again.

An entry becomes dispatchable again only when:

1. its authoritative state changes to another non-terminal state; or
2. its prior dispatch is conclusively known not to have been accepted, through
   an explicit dispatch acknowledgement protocol introduced by a separately
   approved design.

This repair does not introduce the second mechanism. The safe default is to
wait for a state change.

### All roles obey the no-op gate

Manager, planner, executor, and reviewer executions use the same completion
rule:

- the authoritative state-label set changed: pass and record the real
  transition;
- the state-label set did not change: block the issue;
- a required role output is missing: block the issue according to the existing
  role contract.

Any manager-specific completion inference, success handler, or automatic state
advance must be removed. Manager has no completion exception.

### One normal-flow exception: newly created PR

The only code-owned normal state advance is the publish boundary:

1. before execution, the issue is `state/merge-ready`;
2. before execution, the branch has no authoritative open PR;
3. `vibe run --publish` executes;
4. after execution, an authoritative lookup confirms a newly created open PR
   with an identity absent from the before snapshot;
5. the system performs a real `merge-ready -> handoff` label transition.

The exception does not apply when a PR or `pr_ref` already existed before the
execution. A truthy cached `pr_ref` is not proof that the current execution
created a PR. If PR creation succeeds but the label transition fails, the run
does not receive a synthetic success; the issue is blocked with an actionable
reason.

The resulting transition is recorded only after the remote label write is
confirmed.

### State inference belongs only to blocked recovery

`infer_resume_label()` may be called only when all of the following are true:

- authoritative issue-body truth says the issue is blocked;
- the issue is in the blocked recovery operation;
- all dependency blocks have resolved, or an explicit resume operation has
  cleared the blocking reason;
- recovery has enough valid flow context to infer a target.

Ordinary active dispatch, queue collection, missing-flow repair, stale cache
alignment, and orphan detection must not infer or write a normal state.

If blocked recovery cannot verify authoritative truth or cannot obtain valid
context, it remains blocked. It does not fall through into ordinary dispatch.

### Loop accounting survives block and resume

Every confirmed state-label transition in one flow epoch contributes to loop
accounting, including:

- agent or human normal progression observed by the no-op gate;
- entering blocked;
- inferred blocked recovery;
- explicit manual resume;
- the newly-created-PR publish exception.

Blocked recovery must not clear `transition_count` or pair history. Counters are
reset only when a new flow epoch is explicitly created, such as a destructive
rebuild, or when the flow reaches its terminal lifecycle cleanup.

Pair history records only observed or confirmed real transitions. Synthetic
before/after pairs are forbidden. When a configured total or pair limit is
reached, the issue remains blocked and no further normal dispatch occurs.

## Authorized State Writers

The repair treats state writes as an explicit allowlist:

| Writer | Authorized purpose | May infer target? |
| --- | --- | --- |
| Agent or human | Normal business progression | Agent/human decision |
| No-op/block handler | Enter `state/blocked` after a verified contract violation | No |
| Blocked recovery | Leave an authoritative blocked state after its condition resolves | Yes, through `infer_resume_label()` |
| Publish completion | Real `merge-ready -> handoff` after this execution creates a new PR | No; target is fixed by this explicit exception |
| Terminal lifecycle | Confirmed close/done cleanup defined by lifecycle standards | No |

All other code-owned normal state writes are unauthorized and must be removed
or routed through a separately approved business operation.

## Component Boundaries

### Dispatch coordinator

The coordinator owns queue ordering, in-flight idempotency, capacity, session
gates, remote invalidation, and intent emission. It does not own progress
inference.

The dispatch loop handles entries in this order:

1. reload authoritative issue facts;
2. remove terminal or excluded entries;
3. if `waiting_state` equals the authoritative state, retain without emitting;
4. if a live or starting session exists, retain without emitting;
5. run active eligibility checks that return the observed state unchanged;
6. emit one intent and set `waiting_state`.

Blocked issues take a distinct recovery path. They are not treated as ordinary
active candidates whose state happens to be inferred by generic preflight.

### Session registry

Dispatch and execution share one canonical definition of a live execution:

- a running session with a live tmux process; or
- a recent starting session that has not yet acquired a tmux name.

The canonical query must be reused by both layers so that a starting session
cannot be invisible to dispatch but visible to execution deduplication.

### No-op gate and publish completion

The execution shell captures a before snapshot containing the complete state
label set and authoritative open-PR identity. After execution it captures the
same facts again.

The no-op gate evaluates observed deltas. It never fabricates an
`EVENT_STATE_TRANSITIONED` record. The publish exception is a dedicated
completion operation invoked only when the PR delta satisfies its full
preconditions; it writes and confirms the real label transition before the
transition recorder runs.

### Blocked recovery

Blocked truth reconciliation and blocked target selection remain separate
conceptual steps:

1. reconcile body truth, dependency status, label, and cache;
2. if still blocked, return no target;
3. if unblocked, invoke the blocked-only resume resolver;
4. write and confirm the inferred label;
5. record the real transition without resetting the flow epoch counters.

The public API should make the blocked precondition explicit so generic active
preflight cannot accidentally reuse it.

### Transition recorder

One shared recorder accepts a confirmed `(flow_epoch, from_state, to_state,
actor, evidence)` transition. It increments the total count and records the
pair atomically. It contains no business rule for selecting `to_state`.

Callers may ask the recorder whether a proposed code-owned transition would
exceed a limit before writing it. Agent-owned remote changes are observed after
the fact; if the confirmed change crosses the limit, the no-op gate records the
change and blocks further progression.

## Paths to Remove or Restrict

The implementation audit must remove or constrain these behavior classes:

- dispatch of a waiting entry whose authoritative state is unchanged;
- active preflight returning a state derived from flow refs;
- ordinary orphan or missing-flow recovery that force-writes `state/ready`;
- manager completion inference or automatic manager success transitions;
- executor publish success based only on an existing cached `pr_ref`;
- synthetic transition events or history rows;
- unblock logic that clears transition totals or pair history;
- separate dispatch/execution definitions of live sessions.

The audit is behavior-based rather than limited to currently known function
names, because prior refactors may have moved equivalent logic.

## Repair Sequence

### Phase 0: Containment

- Restore waiting-entry idempotency before any further architecture cleanup.
- Make dispatch use the canonical live-session query.
- Disable the cached-`pr_ref` synthetic publish pass.
- Disable ordinary non-blocked auto-resume state writes.

This phase minimizes production loop risk. It may temporarily preserve some
duplicate structure.

### Phase 1: Executable invariant tests

Add regression tests for the business invariants before restructuring code.
The tests must exercise multiple heartbeat ticks and real before/after state
snapshots rather than asserting only helper calls.

### Phase 2: Separate observation from decision

- Make active dispatch qualification return only the observed state.
- Isolate blocked recovery behind a blocked-specific API.
- Delete manager completion inference and generic active-state inference.
- Establish the authorized state-writer boundaries.

### Phase 3: Repair publish completion

- Capture authoritative before/after PR identity.
- Implement the newly-created-PR exception with a real confirmed label write.
- Remove all synthetic publish transitions and stale-`pr_ref` shortcuts.

### Phase 4: Make loop accounting monotonic per flow epoch

- Centralize confirmed transition recording.
- Count blocked entry, blocked recovery, manual resume, and publish completion.
- Stop clearing counters during unblock.
- Reset only through an explicit new epoch or terminal cleanup.

### Phase 5: Delete migration residue

After the invariant suite passes, delete superseded helpers, compatibility
branches, duplicate liveness queries, and stale tests that encode the broken
behavior. Structural FSM and reconciliation primitives remain only where they
respect the boundaries above.

## Verification Matrix

The repair is not complete until all of these behaviors are covered:

| Scenario | Required result |
| --- | --- |
| Same active state for 10 ticks | Exactly one dispatch intent |
| Recent starting session without tmux | No second dispatch intent |
| Active issue has plan/report/verdict/PR refs | Dispatch state remains its observed label |
| Manager returns without changing state | Issue becomes blocked |
| Any worker returns without changing state | Issue becomes blocked |
| Publish starts without PR and creates a new PR | Real `merge-ready -> handoff`, count increments once |
| Publish starts with an existing PR | No exception; unchanged state becomes blocked |
| Cached stale `pr_ref` with no authoritative PR | No publish exception |
| Blocked dependency remains open | Remains blocked, no dispatch |
| Blocked dependency resolves | Inferred recovery transition is real and counted |
| Manual resume | Transition is counted; prior history remains |
| Repeated state pair reaches limit | Further progression blocked |
| Explicit rebuild creates a new flow epoch | Counters reset once |
| Synthetic transition search | No runtime path can emit one |

Targeted tests must include coordinator integration, execution/no-op unit and
integration tests, blocked recovery tests, and transition persistence tests.
Repository lint, type checks for affected modules, `git diff --check`, and the
relevant modularity suite are required. Full regression remains CI-owned unless
the implementation changes shared state-machine primitives broadly enough to
justify a local full run.

## Rollback and Delivery Strategy

Each phase is independently revertible. Containment lands before cleanup.
Behavioral convergence must not be bundled with structural deletions that make
rollback difficult.

If production evidence shows repeated intents after Phase 0, dispatch remains
frozen for waiting entries while diagnostics are collected. The system must not
restore inferred active progression as a fallback.

## Non-goals

- Encoding the preferred manager, planner, executor, or reviewer workflow in
  Python.
- Inferring normal progress from authoritative refs.
- Replacing agent-owned state decisions with a more elaborate code state
  machine.
- Reverting all FSM, blocked truth, or service-layer consolidation work.
- Adding a general dispatch acknowledgement protocol in this repair.
- Optimizing GitHub API usage before correctness and idempotency are restored.
