# Dispatch and No-Op Invariants Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore dispatch idempotency and the no-op business boundary so normal issue progression is agent-owned, state inference is blocked-recovery-only, the sole automatic normal transition requires a newly created PR, and loop counters remain monotonic for a flow epoch.

**Architecture:** Keep unified mechanisms but separate observation from business decision. Dispatch observes the authoritative label and owns only queue/session mechanics; no-op validates real before/after deltas; blocked recovery is the only inferred-state path; a shared transition recorder persists only confirmed transitions and never chooses the next state.

**Tech Stack:** Python 3.13, pytest, SQLite, Pydantic models, GitHub client ports, Loguru, existing Vibe3 domain/services/execution layers.

## Global Constraints

- Normal active dispatch must return the authoritative GitHub state unchanged or reject dispatch; it must never infer a target from refs.
- `waiting_state` is an in-flight lease: an unchanged authoritative state cannot emit another intent.
- Manager, planner, executor, and reviewer all use the same no-op rule: unchanged state becomes blocked.
- The sole code-owned normal transition is a confirmed `state/merge-ready -> state/handoff` when this publish execution starts without an open PR and creates a new open PR.
- A cached or pre-existing `pr_ref` never satisfies the publish exception.
- `infer_resume_label()` is callable only from authoritative blocked recovery or explicit blocked resume.
- Every real transition is counted; synthetic transitions are forbidden.
- Blocked recovery and manual resume must not clear total or pair transition history.
- Transition history resets only for an explicit new flow epoch or terminal cleanup.
- Each task follows TDD and lands as an independently revertible commit.

---

## File Map

### Dispatch and session mechanics

- `src/vibe3/domain/dispatch_coordinator.py`: enforce waiting-entry in-flight idempotency before preflight or intent emission.
- `src/vibe3/orchestra/queue_operations.py`: remove ordinary non-blocked auto-resume and retain only queue selection.
- `src/vibe3/environment/session_registry.py`: provide one issue-level liveness query that includes recent `starting/no-tmux` sessions.
- `tests/vibe3/orchestra/test_dispatch_queue_operations.py`: multi-tick intent idempotency regression.
- `tests/vibe3/orchestra/test_dispatch_safety_gap.py`: remote invalidation behavior for waiting entries.
- `tests/vibe3/services/test_session_registry.py`: canonical starting-session liveness behavior.
- Delete `tests/vibe3/orchestra/test_auto_resume_no_flow.py` and `tests/vibe3/orchestra/test_auto_resume_cooldown.py`: they encode forbidden ordinary-state writes.

### Dispatch qualification boundary

- `src/vibe3/domain/dispatch_preflight.py`: keep active and blocked qualification as separate APIs.
- `src/vibe3/domain/qualify_gate.py`: remove blocked reconciliation from active qualification.
- `tests/vibe3/domain/test_qualify_gate.py`: active issues preserve their observed state despite stale cache/refs.
- `tests/vibe3/domain/test_qualify_gate_blocked_issue.py`: only authoritative blocked issues invoke recovery inference.

### Confirmed transition persistence

- `src/vibe3/clients/sqlite_transition_history_repo.py`: atomic persistence primitive for event, count, and pair history.
- `src/vibe3/services/flow/transition_recorder.py`: business-neutral confirmed-transition recorder and limit result.
- `src/vibe3/services/flow/__init__.py`: public export for the recorder types.
- `tests/vibe3/clients/test_sqlite_transition_history_repo.py`: transaction and epoch-reset tests.
- Create `tests/vibe3/services/test_transition_recorder.py`: recorder count and limit behavior.

### No-op and publish completion

- `src/vibe3/execution/noop_gate.py`: delete synthetic publish success and delegate confirmed transitions to the recorder.
- `src/vibe3/agents/models.py`: add explicit `publish_mode` execution metadata.
- `src/vibe3/roles/run_command.py`: propagate the already-resolved publish mode into `CodeagentCommand`.
- `src/vibe3/execution/codeagent_runner.py`: capture authoritative pre-run open PR identities and pass publish context to no-op.
- Create `src/vibe3/execution/publish_completion.py`: validate the new-PR delta and perform the one authorized real label transition.
- `src/vibe3/execution/__init__.py`: public export for publish completion types.
- `tests/vibe3/execution/test_noop_gate_unit.py`: strict unchanged-state behavior including manager and pre-existing PR.
- Create `tests/vibe3/execution/test_publish_completion.py`: new-PR delta and real-label-write behavior.
- `tests/vibe3/execution/test_codeagent_runner_gate.py`: publish metadata and before snapshot wiring.

### Blocked recovery and flow epochs

- `src/vibe3/services/flow/blocked_state_io.py`: return actual label-write outcomes and expose current authoritative label state.
- `src/vibe3/services/flow/blocked_state_service.py`: enforce blocked-only inference, record real block/resume transitions, and stop clearing history on unblock.
- `src/vibe3/services/task/resume.py`: route auto label selection only through blocked recovery and preserve counters.
- `src/vibe3/services/flow/rebuild.py`: explicitly start a new transition epoch during destructive rebuild.
- `tests/vibe3/services/test_blocked_state_service.py`: blocked-only inference and counted transitions.
- `tests/vibe3/services/test_task_resume_usecase.py`: manual blocked resume preserves history.
- Replace expectations in `tests/vibe3/execution/test_resume_resets_transition_count.py` with monotonic-count assertions.

### Boundary documentation and audit

- `docs/standards/v3/noop-gate-boundary-standard.md`: document the new-PR exception and monotonic flow-epoch counters.
- `docs/standards/v3/blocked-dependency-reconciliation-standard.md`: state that inference is blocked-only and unblock does not reset loop evidence.
- `docs/standards/flow-lifecycle-standard.md`: list the authorized code-owned state writers.

---

### Task 1: Restore Dispatch In-Flight Idempotency and Canonical Liveness

**Files:**
- Modify: `src/vibe3/domain/dispatch_coordinator.py:445-548`
- Modify: `src/vibe3/environment/session_registry.py:332-358`
- Modify: `tests/vibe3/orchestra/test_dispatch_queue_operations.py:213-251`
- Modify: `tests/vibe3/orchestra/test_dispatch_safety_gap.py:18-95`
- Modify: `tests/vibe3/services/test_session_registry.py`

**Interfaces:**
- Consumes: `QueueEntry.waiting_state: str | None`, `IssueInfo.state: IssueState | None`.
- Produces: `SessionRegistryService.get_live_sessions_for_issue(issue_number: int, roles: list[str]) -> list[dict[str, Any]]` with the same liveness semantics as `get_truly_live_sessions_for_target()`.
- Preserves: remote exclusion checks still remove a waiting entry; state equality only suppresses redispatch.

- [ ] **Step 1: Extend the frozen-queue regression through four ticks**

Replace the two-tick assertion with a test that proves the first collection is followed by only one dispatch per issue:

```python
await coordinator.coordinate(tick_id=1)  # collect
await coordinator.coordinate(tick_id=2)  # first dispatch
await coordinator.coordinate(tick_id=3)  # must wait
await coordinator.coordinate(tick_id=4)  # must still wait

assert [(issue.number) for _, issue in emit_calls] == [1, 2]
assert all(entry.waiting_state == "claimed" for entry in coordinator._frozen_queue)
```

- [ ] **Step 2: Add a waiting-entry remote-invalidation regression**

Add a test proving an unchanged waiting entry is removed when a remote exclusion appears without reaching preflight:

```python
def test_waiting_entry_is_observed_for_remote_invalidation(make_coordinator):
    coordinator = make_coordinator("manager")
    coordinator._frozen_queue = [_review_entry()]
    coordinator._load_issue = lambda _n: _review_issue(["someone-else"])
    coordinator._run_dispatch_preflight = MagicMock()

    assert coordinator._dispatch_loop(tick_id=9) == 0
    assert coordinator._frozen_queue == []
    coordinator._run_dispatch_preflight.assert_not_called()
```

- [ ] **Step 3: Add starting-session coverage to the canonical issue query**

Add a registry test with a `starting` row, no `tmux_session`, and a creation time under the existing 60-second stale threshold:

```python
def test_get_live_sessions_for_issue_includes_recent_starting_without_tmux(
    registry, store, recent_starting_session
):
    store.list_live_runtime_sessions.return_value = [recent_starting_session]

    live = registry.get_live_sessions_for_issue(42, ["executor"])

    assert live == [recent_starting_session]
```

- [ ] **Step 4: Run the new tests and verify the current regression**

Run:

```bash
uv run pytest -q \
  tests/vibe3/orchestra/test_dispatch_queue_operations.py \
  tests/vibe3/orchestra/test_dispatch_safety_gap.py \
  tests/vibe3/services/test_session_registry.py
```

Expected: the multi-tick test and recent-starting-session test fail; the remote-invalidation test passes or exposes ordering differences to preserve.

- [ ] **Step 5: Restore the waiting lease before active-session/preflight dispatch checks**

After remote exclusion and terminal checks, retain an unchanged waiting entry:

```python
entry.collected_state = issue.state.value
if entry.waiting_state == issue.state.value:
    append_orchestra_event(
        "dispatcher",
        f"GlobalDispatchCoordinator: retained #{entry.issue_number} "
        f"(in-flight for state={entry.waiting_state})",
    )
    index += 1
    continue
```

Do not move this above remote exclusion or terminal checks.

- [ ] **Step 6: Make issue-level liveness include recent starting sessions**

Use the same stale-starting helper as target-level deduplication:

```python
now = datetime.datetime.now()
for session in sessions:
    if str(session.get("target_id", "")) != str(issue_number):
        continue
    tmux = session.get("tmux_session")
    if tmux:
        if self._has_tmux_session(tmux):
            result.append(session)
    elif not self._handle_stale_starting_session(session, now):
        result.append(session)
```

- [ ] **Step 7: Run dispatch/session tests**

Run the Step 4 command.

Expected: PASS; the four-tick test records exactly two total intents.

- [ ] **Step 8: Commit containment**

```bash
git add src/vibe3/domain/dispatch_coordinator.py \
  src/vibe3/environment/session_registry.py \
  tests/vibe3/orchestra/test_dispatch_queue_operations.py \
  tests/vibe3/orchestra/test_dispatch_safety_gap.py \
  tests/vibe3/services/test_session_registry.py
git commit -m "fix(dispatch): restore in-flight queue idempotency"
```

---

### Task 2: Remove Ordinary Auto-Resume and Active-State Inference

**Files:**
- Modify: `src/vibe3/orchestra/queue_operations.py:14-173`
- Modify: `src/vibe3/domain/qualify_gate.py:58-132`
- Modify: `src/vibe3/domain/dispatch_preflight.py:65-142`
- Delete: `tests/vibe3/orchestra/test_auto_resume_no_flow.py`
- Delete: `tests/vibe3/orchestra/test_auto_resume_cooldown.py`
- Modify: `tests/vibe3/domain/test_qualify_gate.py`
- Modify: `tests/vibe3/domain/test_qualify_gate_blocked_issue.py`

**Interfaces:**
- Consumes: active issue state from `IssueInfo.state` and labels.
- Produces: `_qualify_active(issue) -> IssueState | None` returning only `issue.state` when allowed.
- Restricts: `BlockedStateService.reconcile_blocked()` is reachable from dispatch only through `_qualify_blocked()` / `qualify_blocked_issue()`.

- [ ] **Step 1: Write active-state non-inference regressions**

Add parameterized cases where stale blocked cache and rich refs must not change an active issue's target:

```python
@pytest.mark.parametrize("state", [IssueState.CLAIMED, IssueState.IN_PROGRESS, IssueState.REVIEW, IssueState.MERGE_READY])
def test_active_qualify_never_infers_from_flow_state(state, service, issue):
    issue.state = state
    issue.labels = [state.to_label()]
    flow_state = {
        "flow_status": "blocked",
        "plan_ref": "docs/plan.md",
        "report_ref": "docs/report.md",
        "pr_ref": "https://example/pr/1",
    }

    assert service.run_qualify_gate(
        issue, "task/issue-42", flow_state, issue.labels, state
    ) == state
```

Mock `BlockedStateService` and assert it is not constructed for these active cases.

- [ ] **Step 2: Write blocked-only recovery coverage**

```python
def test_blocked_preflight_is_only_dispatch_recovery_entry(
    preflight, qualify_gate, blocked_issue
):
    issue = blocked_issue
    issue.state = IssueState.BLOCKED
    qualify_gate.qualify_blocked_issue.return_value = IssueState.REVIEW

    decision = preflight.evaluate(issue)

    assert decision.allowed is True
    assert decision.target_state == IssueState.REVIEW
    qualify_gate.qualify_blocked_issue.assert_called_once_with(issue)
    qualify_gate.run_qualify_gate.assert_not_called()
```

- [ ] **Step 3: Run tests and confirm active stale-cache cases fail**

```bash
uv run pytest -q \
  tests/vibe3/domain/test_qualify_gate.py \
  tests/vibe3/domain/test_qualify_gate_blocked_issue.py
```

Expected: active issues with stale blocked signals currently enter reconciliation and fail the new assertion.

- [ ] **Step 4: Delete ordinary auto-resume behavior**

Remove all of the following from `queue_operations.py`:

```python
AUTO_RESUME_COOLDOWN_SECONDS
_COOLDOWN_EVICTION_SECONDS
_last_auto_resume_attempt
_auto_resume_to_ready
```

Replace the no-flow branch in queue selection with a non-mutating skip:

```python
if role.trigger_name != "manager":
    if not branch or not is_auto_task_branch(branch):
        append_orchestra_event(
            "dispatcher",
            f"queue selection skipped #{issue.number}: no active task flow",
        )
        continue
```

Delete the two test files that exist solely to require this forbidden mutation.

- [ ] **Step 5: Restrict active qualification to observed state**

Remove `blocked_signal` and `reconcile_blocked()` from `run_qualify_gate()`. Preserve closed-issue terminalization, active PR-to-review observation if it does not write a guessed state, and worktree health checks. End the active path with:

```python
if not flow_state:
    return trigger_state if trigger_state.to_label() in labels else None

if not self._check_worktree_health(issue, branch, truth):
    return None

return trigger_state if trigger_state.to_label() in labels else None
```

Any helper that writes a normal label while checking active eligibility must be removed rather than relocated.

- [ ] **Step 6: Run qualification and queue tests**

```bash
uv run pytest -q \
  tests/vibe3/domain/test_qualify_gate.py \
  tests/vibe3/domain/test_qualify_gate_blocked_issue.py \
  tests/vibe3/orchestra/test_dispatch_queue_operations.py \
  tests/vibe3/orchestra/test_dispatch_orphan_flow_context.py
```

Expected: PASS and no test expects an active/orphan issue to be force-written to ready.

- [ ] **Step 7: Commit the decision-boundary repair**

```bash
git add -A src/vibe3/orchestra/queue_operations.py \
  src/vibe3/domain/qualify_gate.py \
  src/vibe3/domain/dispatch_preflight.py \
  tests/vibe3/orchestra/test_auto_resume_no_flow.py \
  tests/vibe3/orchestra/test_auto_resume_cooldown.py \
  tests/vibe3/domain/test_qualify_gate.py \
  tests/vibe3/domain/test_qualify_gate_blocked_issue.py
git commit -m "fix(dispatch): keep state inference out of active flows"
```

---

### Task 3: Add an Atomic Confirmed-Transition Recorder

**Files:**
- Modify: `src/vibe3/clients/sqlite_transition_history_repo.py:1-137`
- Create: `src/vibe3/services/flow/transition_recorder.py`
- Modify: `src/vibe3/services/flow/__init__.py`
- Modify: `tests/vibe3/clients/test_sqlite_transition_history_repo.py`
- Create: `tests/vibe3/services/test_transition_recorder.py`

**Interfaces:**
- Produces: `SQLiteClient.record_confirmed_transition(*, branch: str, from_state: str, to_state: str, actor: str, detail: str, refs: dict[str, str]) -> tuple[int, int, int]` returning `(total_count, pair_count, event_id)`.
- Produces: `SQLiteClient.reset_transition_epoch(branch: str) -> None`, used only by explicit rebuild/terminal cleanup.
- Produces: `TransitionRecorder.record_confirmed(*, branch: str, from_state: str, to_state: str, actor: str, issue_number: int) -> TransitionRecordResult`.
- Produces: `TransitionRecorder.would_exceed(branch, from_state, to_state) -> bool` for code-owned transitions before their remote write.

- [ ] **Step 1: Write repository transaction tests**

Add tests for one confirmed transition:

```python
total, pair, event_id = repo.record_confirmed_transition(
    branch="task/issue-42",
    from_state="state/review",
    to_state="state/merge-ready",
    actor="agent:reviewer",
    detail="State changed: state/review -> state/merge-ready",
    refs={"issue": "42"},
)

assert (total, pair) == (1, 1)
assert event_id > 0
assert repo.get_flow_state("task/issue-42")["transition_count"] == 1
assert repo.count_specific_pair(conn, "task/issue-42", "state/review", "state/merge-ready") == 1
```

Also force an insert failure with a temporary trigger and assert count, event, and history all roll back.

- [ ] **Step 2: Write epoch-reset tests**

```python
repo.reset_transition_epoch("task/issue-42")

assert repo.get_flow_state("task/issue-42")["transition_count"] == 0
assert repo.count_transition_pairs(conn, "task/issue-42") == {}
```

- [ ] **Step 3: Run repository tests and verify missing APIs fail**

```bash
uv run pytest -q tests/vibe3/clients/test_sqlite_transition_history_repo.py
```

Expected: FAIL because `record_confirmed_transition` and `reset_transition_epoch` do not exist.

- [ ] **Step 4: Implement atomic persistence in the SQLite repository**

Add a method using one connection transaction. The implementation must insert the event, increment the total, insert history, and read the pair count before commit:

```python
def record_confirmed_transition(
    self,
    *,
    branch: str,
    from_state: str,
    to_state: str,
    actor: str,
    detail: str,
    refs: dict[str, str],
) -> tuple[int, int, int]:
    now = _utcnow_iso()
    conn = self._get_connection()
    with conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE flow_state SET transition_count = "
            "COALESCE(transition_count, 0) + 1, updated_at = ? WHERE branch = ?",
            (now, branch),
        )
        if cursor.rowcount != 1:
            raise ValueError(f"Missing active flow state for {branch}")
        cursor.execute(
            "INSERT INTO flow_events "
            "(branch, event_type, actor, detail, refs, created_at) "
            "VALUES (?, 'state_transitioned', ?, ?, ?, ?)",
            (branch, actor, detail, json.dumps(refs), now),
        )
        event_id = int(cursor.lastrowid)
        cursor.execute(
            "INSERT INTO transition_history "
            "(branch, from_state, to_state, created_at, actor, event_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (branch, from_state, to_state, now, actor, event_id),
        )
        total = int(cursor.execute(
            "SELECT transition_count FROM flow_state WHERE branch = ?", (branch,)
        ).fetchone()[0])
        pair = int(cursor.execute(
            "SELECT COUNT(*) FROM transition_history "
            "WHERE branch = ? AND from_state = ? AND to_state = ?",
            (branch, from_state, to_state),
        ).fetchone()[0])
    return total, pair, event_id
```

Implement `reset_transition_epoch()` in one transaction; do not reuse it from resume/unblock.

- [ ] **Step 5: Write recorder policy tests**

```python
result = recorder.record_confirmed(
    branch="task/issue-42",
    from_state="state/review",
    to_state="state/merge-ready",
    actor="agent:reviewer",
    issue_number=42,
)

assert result.total_count == 1
assert result.pair_count == 1
assert result.total_limit_reached is False
assert result.pair_limit_reached is False
```

Seed total `19` and pair count `3` in separate tests and assert the returned flags use the existing constants `TRANSITION_LIMIT_HARD=20` and `SINGLE_STEP_LIMIT=3`.

- [ ] **Step 6: Implement the business-neutral recorder**

Use immutable results and no target-state inference:

```python
@dataclass(frozen=True)
class TransitionRecordResult:
    total_count: int
    pair_count: int
    total_limit_reached: bool
    pair_limit_reached: bool


class TransitionRecorder:
    def __init__(self, store: SQLiteClient) -> None:
        self._store = store

    def would_exceed(self, branch: str, from_state: str, to_state: str) -> bool:
        flow = self._store.get_flow_state(branch) or {}
        with sqlite3.connect(self._store.db_path) as conn:
            pair = self._store.count_specific_pair(
                conn, branch, from_state, to_state
            )
        return int(flow.get("transition_count", 0) or 0) + 1 >= TRANSITION_LIMIT_HARD or pair >= SINGLE_STEP_LIMIT

    def record_confirmed(
        self,
        *,
        branch: str,
        from_state: str,
        to_state: str,
        actor: str,
        issue_number: int,
    ) -> TransitionRecordResult:
        total, pair, _event_id = self._store.record_confirmed_transition(
            branch=branch,
            from_state=from_state,
            to_state=to_state,
            actor=actor,
            detail=f"State changed: {from_state} -> {to_state}",
            refs={
                "before_state": from_state,
                "after_state": to_state,
                "issue": str(issue_number),
            },
        )
        return TransitionRecordResult(
            total_count=total,
            pair_count=pair,
            total_limit_reached=total >= TRANSITION_LIMIT_HARD,
            pair_limit_reached=pair > SINGLE_STEP_LIMIT,
        )
```

Keep limit constants in one module. Move them from `noop_gate.py` to `transition_recorder.py` and re-export only if compatibility requires it.

- [ ] **Step 7: Run recorder tests**

```bash
uv run pytest -q \
  tests/vibe3/clients/test_sqlite_transition_history_repo.py \
  tests/vibe3/services/test_transition_recorder.py
```

Expected: PASS, including rollback-on-failure.

- [ ] **Step 8: Commit the transition ledger**

```bash
git add src/vibe3/clients/sqlite_transition_history_repo.py \
  src/vibe3/services/flow/transition_recorder.py \
  src/vibe3/services/flow/__init__.py \
  tests/vibe3/clients/test_sqlite_transition_history_repo.py \
  tests/vibe3/services/test_transition_recorder.py
git commit -m "feat(flow): record confirmed transitions atomically"
```

---

### Task 4: Make No-Op Strict for Every L3 Role

**Files:**
- Modify: `src/vibe3/execution/noop_gate.py:47-620`
- Modify: `src/vibe3/execution/codeagent_runner.py:330-390`
- Modify: `tests/vibe3/execution/test_noop_gate_unit.py`
- Modify: `tests/vibe3/execution/test_noop_gate_transition_count.py`
- Modify: `tests/vibe3/execution/test_noop_gate_single_step_limit.py`
- Modify: `tests/vibe3/execution/test_codeagent_runner_gate.py`

**Interfaces:**
- Consumes: `TransitionRecorder.record_confirmed()` from Task 3.
- Produces: strict `apply_unified_noop_gate()` with no cached-PR or synthetic-transition exception.
- Preserves: `_noop_gate_roles = {"manager", "planner", "executor", "reviewer"}` in the execution shell.

- [ ] **Step 1: Replace the synthetic publish test with strict no-op tests**

Delete `test_passes_executor_publish_with_existing_pr`. Add:

```python
@pytest.mark.parametrize("role", ["manager", "planner", "executor", "reviewer"])
def test_unchanged_state_blocks_every_l3_role(role, gate_fixture):
    gate_fixture.after_labels = frozenset({gate_fixture.before_label})

    apply_unified_noop_gate(role=role, **gate_fixture.kwargs)

    gate_fixture.block_fn.assert_called_once()
    assert not any(
        call.args[1] == "state_transitioned"
        for call in gate_fixture.store.add_event.call_args_list
    )
```

For reviewer, seed the required verdict so the test reaches unchanged-state handling. For planner, seed `plan_ref`.

- [ ] **Step 2: Add a no-synthetic-event regression for existing PR refs**

```python
def test_existing_pr_ref_does_not_bypass_executor_noop(gate_fixture):
    gate_fixture.flow_state["pr_ref"] = "https://example/pr/7"
    gate_fixture.after_labels = frozenset({"state/merge-ready"})

    apply_unified_noop_gate(role="executor", **gate_fixture.kwargs)

    gate_fixture.block_fn.assert_called_once()
    gate_fixture.store.record_transition.assert_not_called()
```

- [ ] **Step 3: Run no-op tests and verify old behavior fails**

```bash
uv run pytest -q \
  tests/vibe3/execution/test_noop_gate_unit.py \
  tests/vibe3/execution/test_noop_gate_transition_count.py \
  tests/vibe3/execution/test_noop_gate_single_step_limit.py
```

Expected: strict executor existing-PR test fails because the synthetic branch passes.

- [ ] **Step 4: Delete the synthetic publish branch**

Remove the entire `executor + state/merge-ready + flow_state.pr_ref` block, including its synthetic event and history insertion. The unchanged branch becomes:

```python
if not state_set_changed:
    state_desc = before_state_label or "(no state)"
    store.add_event(
        branch,
        EVENT_STATE_UNCHANGED,
        actor,
        detail=f"State unchanged after {role}: still {state_desc}",
        refs={"state": state_desc, "issue": str(issue_number)},
    )
    _block_fn(
        issue_number=issue_number,
        repo=repo,
        reason="state unchanged",
        actor=actor,
        flow_service=flow_service,
    )
    return
```

- [ ] **Step 5: Replace duplicate transition bookkeeping with the recorder**

After a real state-set delta is observed, call:

```python
transition = TransitionRecorder(store).record_confirmed(
    branch=branch,
    from_state=before_state_label,
    to_state=after_state_label,
    actor=actor,
    issue_number=issue_number,
)
flow_state["transition_count"] = transition.total_count
```

If `transition.total_limit_reached` or `transition.pair_limit_reached`, block further progression after recording the observed real transition. Delete direct SQLite history writes and manual `transition_count += 1` from `noop_gate.py`.

- [ ] **Step 6: Assert the execution shell gates manager**

Add a runner test with `command.role="manager"`, unchanged labels, and `task/issue-*` branch. Assert `apply_unified_noop_gate` is called once. Do not add manager completion inference or a manager-specific target.

- [ ] **Step 7: Run no-op and runner tests**

```bash
uv run pytest -q \
  tests/vibe3/execution/test_noop_gate_unit.py \
  tests/vibe3/execution/test_noop_gate_transition_count.py \
  tests/vibe3/execution/test_noop_gate_single_step_limit.py \
  tests/vibe3/execution/test_codeagent_runner_gate.py
```

Expected: PASS; no test observes a synthetic transition.

- [ ] **Step 8: Commit strict no-op behavior**

```bash
git add src/vibe3/execution/noop_gate.py \
  src/vibe3/execution/codeagent_runner.py \
  tests/vibe3/execution/test_noop_gate_unit.py \
  tests/vibe3/execution/test_noop_gate_transition_count.py \
  tests/vibe3/execution/test_noop_gate_single_step_limit.py \
  tests/vibe3/execution/test_codeagent_runner_gate.py
git commit -m "fix(noop): require real state changes for every role"
```

---

### Task 5: Implement the Newly-Created-PR Publish Exception

**Files:**
- Modify: `src/vibe3/agents/models.py:16-145`
- Modify: `src/vibe3/roles/run_command.py:245-315`
- Modify: `src/vibe3/execution/codeagent_runner.py:58-305,350-385`
- Create: `src/vibe3/execution/publish_completion.py`
- Modify: `src/vibe3/execution/noop_gate.py`
- Modify: `src/vibe3/execution/__init__.py`
- Create: `tests/vibe3/execution/test_publish_completion.py`
- Modify: `tests/vibe3/execution/test_codeagent_runner_gate.py`
- Modify: `tests/vibe3/execution/test_noop_gate_unit.py`

**Interfaces:**
- Produces: `CodeagentCommand.publish_mode: bool = False`.
- Produces: `SyncExecutionContext.before_open_pr_numbers: frozenset[int]`.
- Produces: `PublishCompletionService.try_complete(*, issue_number: int, branch: str, before_state_labels: frozenset[str], before_open_pr_numbers: frozenset[int], actor: str) -> PublishCompletionResult`.
- Consumes: `TransitionRecorder.would_exceed()` and `.record_confirmed()` from Task 3.

- [ ] **Step 1: Write publish completion service tests**

Cover exactly these cases:

```python
def test_new_pr_advances_merge_ready_to_handoff(service):
    service.github.list_prs_for_branch.return_value = [open_pr(number=91)]
    service.labels.confirm_issue_state.return_value = "advanced"

    result = service.try_complete(
        issue_number=42,
        branch="task/issue-42",
        before_state_labels=frozenset({"state/merge-ready"}),
        before_open_pr_numbers=frozenset(),
        actor="agent:executor",
    )

    assert result.completed is True
    assert result.pr_number == 91
    service.labels.confirm_issue_state.assert_called_once_with(
        42, IssueState.HANDOFF, actor="agent:executor", force=False
    )
    service.recorder.record_confirmed.assert_called_once()
```

Add separate tests asserting `completed=False` and no label write when:

- PR 91 existed in the before snapshot;
- cached `pr_ref` exists but GitHub returns no open PR;
- more than one new open PR appears;
- before state is not exactly merge-ready;
- transition budget is exhausted;
- label write returns `blocked` or `confirmed` instead of `advanced`.

- [ ] **Step 2: Run the new service test and verify import failure**

```bash
uv run pytest -q tests/vibe3/execution/test_publish_completion.py
```

Expected: FAIL because `vibe3.execution.publish_completion` does not exist.

- [ ] **Step 3: Implement immutable publish completion results**

```python
@dataclass(frozen=True)
class PublishCompletionResult:
    completed: bool
    pr_number: int | None = None
    reason: str = ""


class PublishCompletionService:
    def __init__(
        self,
        github: PRReadPort,
        labels: LabelService,
        recorder: TransitionRecorder,
    ) -> None:
        self._github = github
        self._labels = labels
        self._recorder = recorder

    def try_complete(
        self,
        *,
        issue_number: int,
        branch: str,
        before_state_labels: frozenset[str],
        before_open_pr_numbers: frozenset[int],
        actor: str,
    ) -> PublishCompletionResult:
        if before_state_labels != frozenset({"state/merge-ready"}):
            return PublishCompletionResult(False, reason="publish did not start in merge-ready")
        if before_open_pr_numbers:
            return PublishCompletionResult(False, reason="open PR existed before publish")
        after = self._github.list_prs_for_branch(branch, state="open")
        new_numbers = {pr.number for pr in after} - set(before_open_pr_numbers)
        if len(new_numbers) != 1:
            return PublishCompletionResult(False, reason="publish did not create exactly one open PR")
        if self._recorder.would_exceed(branch, "state/merge-ready", "state/handoff"):
            return PublishCompletionResult(False, reason="transition limit reached")
        result = self._labels.confirm_issue_state(
            issue_number, IssueState.HANDOFF, actor=actor, force=False
        )
        if result != "advanced":
            return PublishCompletionResult(False, reason=f"handoff transition not applied: {result}")
        pr_number = next(iter(new_numbers))
        self._recorder.record_confirmed(
            branch=branch,
            from_state="state/merge-ready",
            to_state="state/handoff",
            actor=actor,
            issue_number=issue_number,
        )
        return PublishCompletionResult(True, pr_number=pr_number)
```

- [ ] **Step 4: Add explicit publish execution metadata**

Add `publish_mode: bool = False` to `CodeagentCommand` and its factory. In the skill-mode run path, propagate the already computed value:

```python
command = create_codeagent_command(
    role="executor",
    context_builder=context_builder,
    task=instructions or f"Execute skill: {skill}",
    dry_run=dry_run,
    handoff_kind="run",
    handoff_metadata={"skill": skill},
    agent=agent,
    backend=backend,
    model=model,
    config=config,
    branch=branch,
    issue_number=issue_number,
    show_prompt=show_prompt,
    publish_mode=is_publish_path,
)
```

Ensure automatic merge-ready dispatch forwards `--publish` or equivalent metadata into the sync child so `publish_mode=True` is reconstructed there. Add a request-builder assertion in the existing dispatch handler tests.

- [ ] **Step 5: Capture authoritative before-PR identity**

Add `before_open_pr_numbers` to `SyncExecutionContext`. Only for `command.publish_mode`, query:

```python
before_open_pr_numbers = frozenset(
    pr.number
    for pr in GitHubClient().list_prs_for_branch(
        branch, state="open", repo=getattr(self.config, "repo", None)
    )
) if branch and command.publish_mode else frozenset()
```

If this authoritative snapshot fails, record the failure in the context and do not permit the exception. Do not substitute `flow_state.pr_ref`.

- [ ] **Step 6: Invoke the exception only inside unchanged-state handling**

Extend `apply_unified_noop_gate()` with explicit publish inputs. Before ordinary unchanged-state blocking:

```python
if publish_mode:
    publish_result = publish_completion.try_complete(
        issue_number=issue_number,
        branch=branch,
        before_state_labels=effective_before_labels,
        before_open_pr_numbers=before_open_pr_numbers,
        actor=actor,
    )
    if publish_result.completed:
        return
```

On any non-completed result, proceed to the normal state-unchanged block with the publish reason included in event detail.

- [ ] **Step 7: Run publish/no-op/runner tests**

```bash
uv run pytest -q \
  tests/vibe3/execution/test_publish_completion.py \
  tests/vibe3/execution/test_noop_gate_unit.py \
  tests/vibe3/execution/test_codeagent_runner_gate.py \
  tests/vibe3/domain/handlers/test_dispatch.py
```

Expected: PASS; only a before-empty/after-one-new authoritative PR delta advances the label.

- [ ] **Step 8: Commit the sole normal-flow exception**

```bash
git add src/vibe3/agents/models.py \
  src/vibe3/roles/run_command.py \
  src/vibe3/execution/codeagent_runner.py \
  src/vibe3/execution/publish_completion.py \
  src/vibe3/execution/noop_gate.py \
  src/vibe3/execution/__init__.py \
  tests/vibe3/execution/test_publish_completion.py \
  tests/vibe3/execution/test_codeagent_runner_gate.py \
  tests/vibe3/execution/test_noop_gate_unit.py \
  tests/vibe3/domain/handlers/test_dispatch.py
git commit -m "feat(publish): advance only for a newly created PR"
```

---

### Task 6: Restrict Inference to Blocked Recovery and Preserve Loop Evidence

**Files:**
- Modify: `src/vibe3/services/flow/blocked_state_io.py:146-285`
- Modify: `src/vibe3/services/flow/blocked_state_service.py:60-268`
- Modify: `src/vibe3/services/task/resume.py:110-235`
- Modify: `src/vibe3/services/flow/rebuild.py:60-175`
- Modify: `tests/vibe3/services/test_blocked_state_service.py`
- Modify: `tests/vibe3/services/test_task_resume_usecase.py`
- Rewrite: `tests/vibe3/execution/test_resume_resets_transition_count.py`

**Interfaces:**
- Consumes: `TransitionRecorder` and `SQLiteClient.reset_transition_epoch()` from Task 3.
- Produces: `BlockedStateIO.read_issue_state(issue_number: int) -> IssueState | None`.
- Guarantees: `infer_resume_label()` is invoked only when current authoritative state is `IssueState.BLOCKED` and reconciliation proves the block resolved.

- [ ] **Step 1: Replace reset expectations with monotonic resume tests**

Rename the reset test module to describe preservation if repository naming policy permits; otherwise replace its contents. The central assertion is:

```python
before = store.get_flow_state(branch)["transition_count"]
target = service.reconcile_blocked(
    issue_number=42,
    branch=branch,
    clear_reason=True,
    actor="human:resume",
)

assert target == IssueState.READY
assert store.get_flow_state(branch)["transition_count"] == before + 1
assert store.count_specific_pair(
    conn, branch, "state/blocked", "state/ready"
) == 1
```

Seed an existing pair and assert it remains after resume.

- [ ] **Step 2: Add blocked-only inference tests**

```python
def test_reconcile_does_not_infer_for_active_issue(service, labels):
    labels.get_state.return_value = IssueState.REVIEW
    service.store.get_flow_state.return_value = {"plan_ref": "p", "report_ref": "r"}

    result = service.reconcile_blocked(42, "task/issue-42", clear_reason=False)

    assert result is None
    labels.confirm_issue_state.assert_not_called()
```

Also test a genuinely blocked issue with resolved dependencies infers and applies the expected target.

- [ ] **Step 3: Add explicit rebuild epoch-reset coverage**

```python
rebuild.rebuild_issue_flow(
    issue=issue,
    branch="task/issue-42",
    reason="explicit rebuild for damaged scene",
    include_remote=False,
    ensure_worktree=False,
)

store.reset_transition_epoch.assert_called_once_with("task/issue-42")
```

No resume path may call this method.

- [ ] **Step 4: Run blocked/resume tests and verify reset behavior fails**

```bash
uv run pytest -q \
  tests/vibe3/services/test_blocked_state_service.py \
  tests/vibe3/services/test_task_resume_usecase.py \
  tests/vibe3/execution/test_resume_resets_transition_count.py
```

Expected: monotonic assertions fail because current unblock code resets count and clears history.

- [ ] **Step 5: Expose current authoritative label state and write outcomes**

Add:

```python
def read_issue_state(self, issue_number: int) -> IssueState | None:
    return self.label_service.get_state(issue_number)
```

Keep `write_label_state()` returning `"confirmed" | "advanced" | "blocked" | "normalized"`; callers must inspect it before recording a transition.

- [ ] **Step 6: Enforce the blocked recovery precondition**

Immediately before the resolved-block branch can infer:

```python
current_state = self._io.read_issue_state(issue_number)
if current_state != IssueState.BLOCKED:
    logger.bind(
        domain="blocked_state",
        action="reconcile_blocked",
        issue_number=issue_number,
        branch=branch,
    ).warning(
        "Refusing resume inference for issue that is not authoritatively blocked"
    )
    return None
```

Then infer, check `TransitionRecorder.would_exceed()`, apply the label, and record only if the write result proves a real transition:

```python
write_result = self._io.write_label_state(
    issue_number, target, actor=actor, force=True, normalize=True
)
if write_result not in {"advanced", "normalized"}:
    return None
recorder.record_confirmed(
    branch=branch,
    from_state="state/blocked",
    to_state=target.to_label(),
    actor=actor,
    issue_number=issue_number,
)
```

If the transition budget is exhausted, retain blocked truth and label.

- [ ] **Step 7: Record entering blocked and stop resetting on unblock**

When a non-blocked authoritative label is successfully advanced to blocked,
record that real pair through `TransitionRecorder`. Do not record when the
label was already blocked.

Delete these unblock behaviors from both `blocked_state_service.py` and
`blocked_state_io.py`:

```python
update_kwargs["transition_count"] = 0
self.store.clear_transition_history(conn, branch)
```

Preserve unrelated AUP/no-op retry counter policies only if their standards
still require them.

- [ ] **Step 8: Restrict task resume and reset only on rebuild**

In `TaskResumeUsecase`, reject inferred auto-label selection unless current
state is blocked. Explicit human labels still pass through the blocked resume
operation and are counted as `blocked -> chosen-label`.

In destructive `FlowRebuildUsecase`, call:

```python
self._store.reset_transition_epoch(branch)
```

after the old scene is removed and before the fresh flow is dispatched. This is
the only non-terminal reset added by this plan.

- [ ] **Step 9: Run blocked/rebuild/no-op regression tests**

```bash
uv run pytest -q \
  tests/vibe3/services/test_blocked_state_io.py \
  tests/vibe3/services/test_blocked_state_service.py \
  tests/vibe3/services/test_blocked_state_resume_normalization.py \
  tests/vibe3/services/test_task_resume_usecase.py \
  tests/vibe3/services/test_task_resume_usecase_blocked_sync.py \
  tests/vibe3/execution/test_resume_resets_transition_count.py \
  tests/vibe3/execution/test_noop_gate_transition_count.py
```

Expected: PASS; resume increments rather than resets transition evidence.

- [ ] **Step 10: Commit blocked-only inference and flow epochs**

```bash
git add src/vibe3/services/flow/blocked_state_io.py \
  src/vibe3/services/flow/blocked_state_service.py \
  src/vibe3/services/task/resume.py \
  src/vibe3/services/flow/rebuild.py \
  tests/vibe3/services/test_blocked_state_io.py \
  tests/vibe3/services/test_blocked_state_service.py \
  tests/vibe3/services/test_blocked_state_resume_normalization.py \
  tests/vibe3/services/test_task_resume_usecase.py \
  tests/vibe3/services/test_task_resume_usecase_blocked_sync.py \
  tests/vibe3/execution/test_resume_resets_transition_count.py
git commit -m "fix(blocked): keep inference and loop evidence recovery-scoped"
```

---

### Task 7: Audit State Writers, Update Standards, and Run the Integrated Gate

**Files:**
- Modify: `docs/standards/v3/noop-gate-boundary-standard.md`
- Modify: `docs/standards/v3/blocked-dependency-reconciliation-standard.md`
- Modify: `docs/standards/flow-lifecycle-standard.md`
- Modify only if audit finds violations: state-writing runtime files identified by the commands below.
- Test only if audit finds violations: nearest behavioral test for each removed writer.

**Interfaces:**
- Consumes: all boundaries established in Tasks 1-6.
- Produces: standards that describe the implemented behavior and an audit showing no unauthorized normal state writer remains.

- [ ] **Step 1: Audit every state-inference and force-write call site**

Run:

```bash
rg -n "infer_resume_label|confirm_issue_state|write_label_state|\.transition\(" src/vibe3
rg -n "force=True|IssueState\.(READY|CLAIMED|HANDOFF|IN_PROGRESS|REVIEW|MERGE_READY)" src/vibe3
rg -n "synthetic|state_transitioned" src/vibe3/execution src/vibe3/domain src/vibe3/orchestra
```

Classify every runtime write against the design allowlist:

```text
agent/human normal progression
enter blocked
blocked recovery
new-PR publish completion
terminal lifecycle
```

Any unmatched writer receives a failing behavioral test and is deleted or
routed through one of the explicit operations. Do not add a broader allowlist.

- [ ] **Step 2: Audit manager completion behavior**

Run:

```bash
rg -n "manager.*(complete|completion|success|target_state)|must_change|auto.*handoff" src/vibe3
```

For every match, verify it is prompt/context construction or no-op validation,
not code-owned progression. Remove any manager-specific completion inference
and add a regression to `tests/vibe3/execution/test_codeagent_runner_gate.py`
showing unchanged manager state blocks.

- [ ] **Step 3: Update the no-op boundary standard**

Add exact normative language:

```markdown
- All L3 roles, including manager, must leave their starting state or become blocked.
- The sole code-owned normal transition is merge-ready -> handoff when the
  current publish execution starts without an open PR and creates one.
- Existing pr_ref or an already-open PR does not satisfy this exception.
- Synthetic transition events are forbidden.
```

- [ ] **Step 4: Update blocked reconciliation and lifecycle standards**

Document:

```markdown
- Resume inference requires authoritative state/blocked at entry.
- Active dispatch never calls infer_resume_label().
- Block and resume transitions contribute to total and pair loop accounting.
- Unblock does not reset loop evidence; explicit rebuild starts a new flow epoch.
```

Include the authorized state-writer table from the approved design.

- [ ] **Step 5: Run targeted integrated verification**

```bash
uv run pytest -q \
  tests/vibe3/orchestra/test_dispatch_queue_operations.py \
  tests/vibe3/orchestra/test_dispatch_safety_gap.py \
  tests/vibe3/services/test_session_registry.py \
  tests/vibe3/domain/test_qualify_gate.py \
  tests/vibe3/domain/test_qualify_gate_blocked_issue.py \
  tests/vibe3/clients/test_sqlite_transition_history_repo.py \
  tests/vibe3/services/test_transition_recorder.py \
  tests/vibe3/execution/test_noop_gate_unit.py \
  tests/vibe3/execution/test_noop_gate_transition_count.py \
  tests/vibe3/execution/test_noop_gate_single_step_limit.py \
  tests/vibe3/execution/test_publish_completion.py \
  tests/vibe3/execution/test_codeagent_runner_gate.py \
  tests/vibe3/services/test_blocked_state_service.py \
  tests/vibe3/services/test_task_resume_usecase.py
```

Expected: PASS.

- [ ] **Step 6: Run static and modularity verification**

```bash
uv run ruff check src/vibe3 tests/vibe3
uv run black --check src/vibe3 tests/vibe3
uv run mypy \
  src/vibe3/domain/dispatch_coordinator.py \
  src/vibe3/domain/dispatch_preflight.py \
  src/vibe3/domain/qualify_gate.py \
  src/vibe3/environment/session_registry.py \
  src/vibe3/execution/noop_gate.py \
  src/vibe3/execution/publish_completion.py \
  src/vibe3/services/flow/transition_recorder.py \
  src/vibe3/services/flow/blocked_state_service.py
uv run pytest -q tests/vibe3/test_modularity.py tests/vibe3/test_module_api.py
git diff --check
```

If the exact modularity filenames differ, use `rg --files tests/vibe3 | rg 'modular|module_api'` and run every returned guard file. Expected: all commands exit 0.

- [ ] **Step 7: Run the broad affected subsystem suite**

```bash
uv run pytest -q \
  tests/vibe3/domain \
  tests/vibe3/execution \
  tests/vibe3/orchestra \
  tests/vibe3/services \
  tests/vibe3/clients/test_sqlite_transition_history_repo.py
```

Expected: PASS. Do not weaken a failing behavioral test merely to preserve the refactor; compare it against the approved invariants.

- [ ] **Step 8: Commit standards and final audit cleanup**

```bash
git add docs/standards/v3/noop-gate-boundary-standard.md \
  docs/standards/v3/blocked-dependency-reconciliation-standard.md \
  docs/standards/flow-lifecycle-standard.md
git add src/vibe3 tests/vibe3
git commit -m "docs(standards): codify dispatch and noop invariants"
```

Before the broad `git add`, inspect `git status --short` and revert no files;
stage only audit fixes that were intentionally made in this task. If the audit
changes no runtime files, omit `git add src/vibe3 tests/vibe3`.

---

## Completion Evidence

Before declaring the repair complete, capture all of the following in the final handoff:

- the four-tick dispatch test output proving one intent per unchanged entry;
- the starting/no-tmux liveness test output;
- the strict manager/worker no-op test output;
- the publish before/after PR identity tests;
- the blocked resume monotonic counter and pair-history tests;
- the state-writer audit classification;
- targeted, static, modularity, and broad subsystem suite results;
- `git status --short` showing only intentional changes or a clean tree.

Do not claim success from the former two-tick queue test or from a synthetic event assertion.
