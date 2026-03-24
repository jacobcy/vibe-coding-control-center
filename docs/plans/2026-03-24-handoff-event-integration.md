# Handoff Event Integration Plan

**Date**: 2026-03-24
**Author**: AI Agent
**Status**: Draft for Review

## Overview

Integrate event writing into `plan`, `run`, `review` commands so that all agent executions are recorded in the handoff system.

## Current State Analysis

### What Works

| Component | Status | Notes |
|-----------|--------|-------|
| `review.py` | ✅ Writes `handoff_review` | `_record_review_event()` at line 38-50 |
| `handoff_recorder.py` | ✅ Service exists | `record_handoff()` writes `handoff_{type}` event |
| `handoff_service.py` | ✅ Service exists | `record_plan/report/audit()` methods |
| `flow_events` table | ✅ Has `refs` column | Can store structured JSON |
| `handoff show` | ✅ Reads events | Displays agent chain from flow_state |
| `flow show` | ✅ Shows timeline | Displays events chronologically |

### What Needs Work

| Component | Issue | Priority |
|-----------|-------|----------|
| `plan.py` | Does NOT write events/files | High |
| `run.py` | Does NOT write events/files | High |
| `review.py` | Does NOT write output file | Medium |
| `flow new` | No `--spec` option | Medium |
| `plan spec` | Does NOT write `spec_ref` | Low |
| Naming | `handoff_report` vs `handoff_run` | Low |

## Implementation Plan

### Phase 1: `flow new --spec`

**File**: `src/vibe3/commands/flow.py`

**Change**: Add `--spec` option to `new()` command

```python
# Current signature
def new(
    name: Annotated[str, typer.Argument(help="Flow name")],
    task: Annotated[str | None, typer.Option(help="Task ID to bind")] = None,
    actor: Annotated[str, typer.Option(help="Actor creating the flow")] = "claude",
    ...
) -> None:

# After change
def new(
    name: Annotated[str, typer.Argument(help="Flow name")],
    task: Annotated[str | None, typer.Option(help="Task ID to bind")] = None,
    spec: Annotated[str | None, typer.Option("--spec", help="Spec file path")] = None,
    actor: Annotated[str, typer.Option(help="Actor creating the flow")] = "claude",
    ...
) -> None:
    # ... after creating flow ...
    if spec:
        store = SQLiteClient()
        store.update_flow_state(branch, spec_ref=spec, latest_actor=actor)
        store.add_event(branch, "spec_bound", actor, detail=f"Spec bound: {spec}")
```

**Required changes**:
1. Add `spec` parameter (line ~38)
2. After `service.create_flow()`, add spec_ref handling
3. Write `spec_bound` event

---

### Phase 2: `plan task` Event Writing

**File**: `src/vibe3/commands/plan.py`

**Change**: Add event writing after plan execution

**New function to add** (after line 46):

```python
def _get_handoff_dir() -> Path:
    """Get handoff directory for current branch."""
    from vibe3.utils.git_helpers import get_branch_handoff_dir
    git_dir = GitClient().get_git_common_dir()
    branch = GitClient().get_current_branch()
    handoff_dir = get_branch_handoff_dir(git_dir, branch)
    handoff_dir.mkdir(parents=True, exist_ok=True)
    return handoff_dir


def _record_plan_event(
    plan_content: str,
    config: VibeConfig,
    plan_file: Path | None = None,
) -> Path:
    """Record plan execution to handoff.

    Args:
        plan_content: The plan output from agent
        config: VibeConfig for actor info
        plan_file: Optional pre-determined file path

    Returns:
        Path to the saved plan file
    """
    from datetime import datetime
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.utils.git_helpers import get_branch_handoff_dir

    git = GitClient()
    branch = git.get_current_branch()
    handoff_dir = _get_handoff_dir()

    # Generate timestamp-based filename
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    if plan_file is None:
        plan_file = handoff_dir / f"plan-{timestamp}.md"

    # Save plan content
    plan_file.write_text(plan_content, encoding="utf-8")

    # Construct actor string
    plan_config = getattr(config, "plan", None)
    if plan_config and hasattr(plan_config, "agent_config"):
        ac = plan_config.agent_config
        agent = ac.agent if hasattr(ac, "agent") else "planner"
        model = ac.model if hasattr(ac, "model") else None
        actor = f"{agent}/{model}" if model else agent
    else:
        actor = "planner"

    # Write event and update state
    store = SQLiteClient()
    store.add_event(
        branch,
        "handoff_plan",
        actor,
        detail=f"Plan generated: {plan_file.name}",
        refs={"ref": str(plan_file), "agent": agent, "model": model},
    )
    store.update_flow_state(branch, plan_ref=str(plan_file), planner_actor=actor)

    return plan_file
```

**Modifications to `_run_plan()`** (line 74-113):

```python
def _run_plan(
    request: PlanRequest,
    config: VibeConfig,
    dry_run: bool,
    message: str | None,
    agent: str | None,
    backend: str | None,
    model: str | None,
) -> None:
    """Execute plan generation."""
    # ... existing code ...

    result = run_review_agent(prompt_file_content, options, task=task, dry_run=dry_run)

    if dry_run:
        return

    # NEW: Save plan and record event
    plan_content = result.stdout
    plan_file = _record_plan_event(plan_content, config)

    typer.echo(f"\n📄 Plan saved to: {plan_file}")
    typer.echo("\n" + plan_content)
```

---

### Phase 3: `plan spec` Write `spec_ref`

**File**: `src/vibe3/commands/plan.py`

**Change**: Write `spec_ref` after plan from spec

**Modifications to `spec()` command** (line 167-223):

```python
@app.command()
def spec(
    file: Annotated[Optional[Path], typer.Option("--file", "-f", help="Path to spec file")] = None,
    msg: Annotated[Optional[str], typer.Option("--msg", help="Spec description")] = None,
    ...
) -> None:
    # ... existing validation ...

    # NEW: If file provided, write spec_ref
    if file:
        from vibe3.clients.sqlite_client import SQLiteClient
        from vibe3.clients.git_client import GitClient
        store = SQLiteClient()
        git = GitClient()
        branch = git.get_current_branch()
        store.update_flow_state(branch, spec_ref=str(file.resolve()))
        store.add_event(branch, "spec_bound", "user", detail=f"Spec bound: {file}")

    _run_plan(request, config, dry_run, message, agent, backend, model)
```

---

### Phase 4: `run execute` Event Writing

**File**: `src/vibe3/commands/run.py`

**Change**: Add event writing after run execution

**New function to add** (after line 47):

```python
def _get_handoff_dir() -> Path:
    """Get handoff directory for current branch."""
    from vibe3.utils.git_helpers import get_branch_handoff_dir
    git_dir = GitClient().get_git_common_dir()
    branch = GitClient().get_current_branch()
    handoff_dir = get_branch_handoff_dir(git_dir, branch)
    handoff_dir.mkdir(parents=True, exist_ok=True)
    return handoff_dir


def _record_run_event(
    run_content: str,
    config: VibeConfig,
    plan_file: str,
    run_file: Path | None = None,
) -> Path:
    """Record run execution to handoff.

    Args:
        run_content: The run output from agent
        config: VibeConfig for actor info
        plan_file: The plan file that was executed
        run_file: Optional pre-determined file path

    Returns:
        Path to the saved run file
    """
    from datetime import datetime
    from vibe3.clients.sqlite_client import SQLiteClient

    git = GitClient()
    branch = git.get_current_branch()
    handoff_dir = _get_handoff_dir()

    # Generate timestamp-based filename
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    if run_file is None:
        run_file = handoff_dir / f"run-{timestamp}.md"

    # Save run content
    run_file.write_text(run_content, encoding="utf-8")

    # Construct actor string
    run_config = getattr(config, "run", None)
    if run_config and hasattr(run_config, "agent_config"):
        ac = run_config.agent_config
        agent = ac.agent if hasattr(ac, "agent") else None
        backend = ac.backend if hasattr(ac, "backend") else None
        model = ac.model if hasattr(ac, "model") else None
        if agent:
            actor = f"{agent}/{model}" if model else agent
        else:
            actor = backend if backend else "executor"
    else:
        actor = "executor"

    # Write event and update state
    store = SQLiteClient()
    store.add_event(
        branch,
        "handoff_run",
        actor,
        detail=f"Run completed: {run_file.name}",
        refs={"ref": str(run_file), "plan_ref": plan_file, "agent": agent, "model": model},
    )
    store.update_flow_state(branch, report_ref=str(run_file), executor_actor=actor)

    return run_file
```

**Modifications to `_run_execution()`** (line 81-117):

```python
def _run_execution(
    plan_file: str,
    config: VibeConfig,
    dry_run: bool,
    message: str | None,
    agent: str | None,
    backend: str | None,
    model: str | None,
) -> None:
    """Execute plan."""
    # ... existing code ...

    result = run_review_agent(prompt_file_content, options, task=task, dry_run=dry_run)

    if dry_run:
        return

    # NEW: Save run output and record event
    run_content = result.stdout
    run_file = _record_run_event(run_content, config, plan_file)

    typer.echo(f"\n📄 Run output saved to: {run_file}")
    typer.echo("\n" + run_content)
```

---

### Phase 5: `review` Write Output File

**File**: `src/vibe3/commands/review.py`

**Change**: Save review output to file

**Modification to `_record_review_event()`** (line 38-50):

```python
def _record_review_event(
    review: ParsedReview,
    actor: str,
    review_content: str | None = None,
) -> Path | None:
    """Record review to handoff.

    Args:
        review: Parsed review result
        actor: Actor string (agent/model)
        review_content: Optional review output to save

    Returns:
        Path to the saved review file, or None if failed
    """
    from datetime import datetime
    from pathlib import Path
    from vibe3.utils.git_helpers import get_branch_handoff_dir

    store = SQLiteClient()
    git = GitClient()
    try:
        branch = git.get_current_branch()
    except Exception:
        return None

    # Determine handoff directory
    git_dir = git.get_git_common_dir()
    handoff_dir = get_branch_handoff_dir(git_dir, branch)
    handoff_dir.mkdir(parents=True, exist_ok=True)

    # Generate timestamp-based filename
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    review_file = handoff_dir / f"review-{timestamp}.md"

    # Save review content if provided
    if review_content:
        review_file.write_text(review_content, encoding="utf-8")

    # Write event
    store.add_event(
        branch,
        "handoff_review",
        actor,
        detail=f"Verdict: {review.verdict}, {len(review.comments)} comments",
        refs={"ref": str(review_file), "verdict": review.verdict},
    )
    store.update_flow_state(branch, reviewer_actor=actor, audit_ref=str(review_file))

    return review_file
```

**Modification to `_run_review()`** (line 53-101):

```python
def _run_review(
    request: ReviewRequest,
    config: VibeConfig,
    dry_run: bool,
    message: str | None,
) -> None:
    # ... existing code ...

    raw = result.stdout
    review = parse_codex_review(raw)

    typer.echo(f"\n=== Verdict: {review.verdict} ===")

    # NEW: Pass review content to record function
    _record_review_event(
        review,
        actor=f"{config.review.agent_config.agent}/{config.review.agent_config.model}",
        review_content=raw,
    )

    if review.verdict == "BLOCK":
        raise typer.Exit(1)
```

---

### Phase 6: Naming Unification

**Files to change**:

1. **`src/vibe3/services/handoff_recorder.py`**:
   - Change `handoff_type="report"` → `handoff_type="run"` in docstring/comments
   - Function `record_report()` → keep as alias, add `record_run()`

2. **`src/vibe3/services/handoff_service.py`**:
   - Keep `record_report()` for backward compatibility
   - Add `record_run()` as preferred method

3. **`src/vibe3/ui/flow_ui.py`**:
   - Already has `handoff_run` in color mapping (line 168) ✅

**Note**: Keep `handoff_report` as alias to avoid breaking existing code.

---

## File Structure After Implementation

```
.git/vibe3/handoff/<branch-hash>/
├── current.md              # Human handoff notes (manual via vibe3 handoff append)
├── plan-2026-03-24T10:30:00.md    # vibe3 plan task output
├── plan-2026-03-25T14:20:00.md    # subsequent plan runs
├── run-2026-03-24T11:00:00.md     # vibe3 run execute output
├── run-2026-03-24T15:30:00.md     # subsequent run executions
└── review-2026-03-24T12:00:00.md  # vibe3 review pr output
```

## Database Events After Implementation

```sql
-- Example events in flow_events table
SELECT * FROM flow_events WHERE branch = 'feature-x';

-- Results:
-- | event_type     | actor              | detail                    | refs                                        |
-- |----------------|--------------------|---------------------------|---------------------------------------------|            | handoff_plan   | planner/opus      | Plan generated: plan-2026-03-24T10:30:00.md | {"ref": ".git/vibe3/handoff/.../plan-...", "model": "opus"} |
-- | handoff_run    | executor/sonnet    | Run completed: run-2026-03-24T11:00:00.md | {"ref": ".git/vibe3/...", "plan_ref": "..."} |
-- | handoff_review | reviewer/sonnet    | Verdict: PASS, 3 comments | {"ref": ".git/vibe3/.../review-...", "verdict": "PASS"} |
```

## Testing Plan

1. **Unit tests** for new helper functions:
   - `test_record_plan_event()`
   - `test_record_run_event()`
   - `test_record_review_event()`

2. **Integration tests**:
   - Run `vibe3 plan task` and verify:
     - Event written to `flow_events`
     - File saved to `.git/vibe3/handoff/`
     - `plan_ref` updated in `flow_state`
   - Run `vibe3 run execute` and verify same pattern
   - Run `vibe3 review pr` and verify same pattern

3. **Manual verification**:
   - `vibe3 flow show` displays timeline with events
   - `vibe3 handoff show` displays agent chain with file refs

## Backward Compatibility

- Keep `handoff_report` event type as alias for `handoff_run`
- Keep `record_report()` method as alias for `record_run()`
- Existing `vibe3 handoff plan/report/audit` commands continue to work

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Handoff directory creation fails | Add `mkdir(parents=True, exist_ok=True)` |
| GitClient fails in event recording | Try/except with graceful return |
| File write fails | Log error, continue without blocking main flow |
| Large file content | Consider truncation or external storage for very large outputs |

## Summary

This plan integrates event writing into all agent execution commands (`plan`, `run`, `review`), ensuring that:
1. Every execution saves its output to `.git/vibe3/handoff/<branch>/`
2. Every execution writes an event to `flow_events` table
3. Every execution updates the relevant ref field in `flow_state`
4. `vibe3 flow show` displays the complete timeline
5. `vibe3 handoff show` displays the agent chain with file references