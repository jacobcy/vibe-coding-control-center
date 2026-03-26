# Refactor Plan: Unify run/plan/review Commands Architecture

## Goal
Eliminate architectural duplication across run/plan/review commands (~400-500 lines reduction) by extracting shared infrastructure and consolidating services.

## Current Issues
1. **CLI Options Duplication (3x)**: `_TRACE_OPT`, `_DRY_RUN_OPT`, `_AGENT_OPT` defined identically in run.py/plan.py/review.py
2. **Handoff Recording Duplication (3x)**: `_record_run_event()`, `record_plan_event()`, `_record_review_event()` follow same pattern
3. **Context Builder Fragmentation**: 3 separate builders with duplicated sections
4. **Model Hierarchy Confusion**: `AgentExecutionRequest` wraps `ReviewAgentOptions` unnecessarily
5. **Missing Handoff UI**: No dedicated handoff query/display module

## Phase 1: Extract Command Infrastructure (LOW RISK)

### Task 1.1: Create shared CLI options module
**File**: `src/vibe3/commands/command_options.py`

```python
"""Shared CLI option definitions for all agent commands."""

from typing import Annotated, Optional
import typer

_TRACE_OPT = Annotated[bool, typer.Option("--trace", help="Enable call tracing + DEBUG logs")]
_DRY_RUN_OPT = Annotated[bool, typer.Option("--dry-run", help="Print command without executing")]
_AGENT_OPT = Annotated[Optional[str], typer.Option("--agent", help="Override agent preset")]
_BACKEND_OPT = Annotated[Optional[str], typer.Option("--backend", help="Override backend")]
_MODEL_OPT = Annotated[Optional[str], typer.Option("--model", help="Override model")]

def ensure_flow_for_current_branch() -> tuple[FlowService, str]:
    """Auto-ensure flow for non-main branches.

    Returns:
        Tuple of (flow_service, branch_name)

    Raises:
        typer.Exit: If on main branch or flow creation fails
    """
    from vibe3.clients.git_client import GitClient
    from vibe3.services.flow_service import FlowService
    from vibe3.models.flow import MainBranchProtectedError

    git = GitClient()
    branch = git.get_current_branch()
    flow_service = FlowService()

    try:
        flow_service.ensure_flow_for_branch(branch)
    except MainBranchProtectedError as e:
        import typer
        typer.echo(f"Error: {e}\n", err=True)
        typer.echo("Tip: Create a feature branch first:", err=True)
        typer.echo("  vibe3 flow new <branch-name> -c", err=True)
        raise typer.Exit(1)

    return flow_service, branch
```

**Actions**:
1. Create file with above content
2. Import in run.py, plan.py, review.py
3. Replace duplicated option definitions

### Task 1.2: Refactor run.py to use shared options
**File**: `src/vibe3/commands/run.py`

**Changes**:
- Remove lines 37-57 (option definitions)
- Add: `from vibe3.commands.command_options import _TRACE_OPT, _DRY_RUN_OPT, _AGENT_OPT, _BACKEND_OPT, _MODEL_OPT, ensure_flow_for_current_branch`
- Replace lines 331-342 with: `flow_service, branch = ensure_flow_for_current_branch()`

### Task 1.3: Refactor plan.py to use shared options
**File**: `src/vibe3/commands/plan.py`

**Changes**:
- Remove lines 26-44 (option definitions)
- Add: `from vibe3.commands.command_options import _TRACE_OPT, _DRY_RUN_OPT, _AGENT_OPT, _BACKEND_OPT, _MODEL_OPT, ensure_flow_for_current_branch`
- Replace lines 82-89 with: `flow_service, branch = ensure_flow_for_current_branch()`

### Task 1.4: Refactor review.py to use shared options
**File**: `src/vibe3/commands/review.py`

**Changes**:
- Remove lines 37-42 (option definitions)
- Add: `from vibe3.commands.command_options import _TRACE_OPT, _DRY_RUN_OPT, _AGENT_OPT, _BACKEND_OPT, _MODEL_OPT, ensure_flow_for_current_branch`
- Replace lines 279-286 with: `flow_service, branch = ensure_flow_for_current_branch()`

**Expected Impact**: ~120 lines duplication eliminated

---

## Phase 2: Unify Handoff Recording (MEDIUM RISK)

### Task 2.1: Create unified handoff recorder
**File**: `src/vibe3/services/handoff_recorder_unified.py`

```python
"""Unified handoff recording for all agent types."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal
import re

from vibe3.models.review_runner import ReviewAgentOptions
from vibe3.services.handoff_event_service import (
    create_handoff_artifact,
    persist_handoff_event,
)
from vibe3.services.review_runner import (
    format_agent_actor,
    resolve_actor_backend_model,
)


@dataclass
class HandoffRecord:
    """Generic handoff record for all agent types."""
    kind: Literal["plan", "run", "review"]
    content: str
    options: ReviewAgentOptions
    session_id: str | None = None
    metadata: dict[str, str] | None = None  # kind-specific extra data


def parse_modified_files(content: str) -> list[str]:
    """Extract modified files from agent output.

    Pattern matches:
    ### Modified Files
    - file/path/one.py: description
    - file/path/two.py: description
    """
    match = re.search(
        r"### Modified Files\s*([\s\S]*?)(?:\n###|\Z)",
        content,
        re.IGNORECASE
    )
    if not match:
        return []

    files_section = match.group(1)
    file_matches = re.findall(
        r"^-\s*([^:\]]+)(?::|\])?",
        files_section,
        re.MULTILINE
    )
    return [f.strip() for f in file_matches if f.strip()]


def parse_review_verdict(content: str) -> str | None:
    """Extract review verdict from review output.

    Pattern matches: VERDICT: PASS/FAIL
    """
    match = re.search(r"VERDICT:\s*(PASS|FAIL)", content, re.IGNORECASE)
    return match.group(1).upper() if match else None


def record_handoff_unified(record: HandoffRecord) -> Path | None:
    """Record handoff event with unified logic.

    Common pattern:
    1. Create artifact with kind prefix
    2. Parse content for metadata
    3. Build refs dict
    4. Persist event with flow updates
    """
    # 1. Create artifact
    artifact = create_handoff_artifact(record.kind, record.content)
    if artifact is None:
        return None

    branch, artifact_file = artifact

    # 2. Extract metadata
    actor = format_agent_actor(record.options)
    backend, model = resolve_actor_backend_model(record.options)

    # 3. Build refs
    refs: dict[str, str] = {
        "ref": str(artifact_file),
        "backend": backend,
    }
    if model:
        refs["model"] = model
    if record.session_id:
        refs["session_id"] = record.session_id

    # 4. Kind-specific metadata
    detail_parts = [f"{record.kind.capitalize()} completed: {artifact_file.name}"]

    if record.kind == "run":
        modified_files = parse_modified_files(record.content)
        if modified_files:
            refs["modified_files"] = ",".join(modified_files)
            refs["modified_count"] = str(len(modified_files))
            detail_parts.append(f"Modified {len(modified_files)} files:")
            for f in modified_files[:3]:
                detail_parts.append(f"  - {f}")
            if len(modified_files) > 3:
                detail_parts.append(f"  ... and {len(modified_files) - 3} more")

    elif record.kind == "review":
        verdict = parse_review_verdict(record.content)
        if verdict:
            refs["verdict"] = verdict
            detail_parts.append(f"Verdict: {verdict}")

    # Add metadata if provided
    if record.metadata:
        refs.update(record.metadata)

    detail = "\n".join(detail_parts)

    # 5. Flow state updates
    flow_state_updates = {
        f"{record.kind}_ref": str(artifact_file),
        f"{record.kind}er_actor": actor,  # planner_actor, executor_actor, reviewer_actor
        f"{record.kind}er_session_id": record.session_id,
    }

    # 6. Persist event
    persist_handoff_event(
        branch=branch,
        event_type=f"handoff_{record.kind}",
        actor=actor,
        detail=detail,
        refs=refs,
        flow_state_updates=flow_state_updates,
    )

    return artifact_file
```

**Actions**:
1. Create file with above implementation
2. Refactor run.py, plan_helpers.py, review.py to use `record_handoff_unified()`

### Task 2.2: Refactor run.py to use unified recorder
**File**: `src/vibe3/commands/run.py`

**Changes**:
- Remove `_record_run_event()` function (lines 60-133)
- Add: `from vibe3.services.handoff_recorder_unified import HandoffRecord, record_handoff_unified`
- Replace call: `record_handoff_unified(HandoffRecord(kind="run", content=run_content, options=options, session_id=outcome.effective_session_id))`

### Task 2.3: Refactor plan_helpers.py to use unified recorder
**File**: `src/vibe3/commands/plan_helpers.py`

**Changes**:
- Remove `record_plan_event()` function (lines 82-124)
- Add: `from vibe3.services.handoff_recorder_unified import HandoffRecord, record_handoff_unified`
- Update `run_plan()` to use unified recorder

### Task 2.4: Refactor review.py to use unified recorder
**File**: `src/vibe3/commands/review.py`

**Changes**:
- Remove `_record_review_event()` function (lines 45-74)
- Add: `from vibe3.services.handoff_recorder_unified import HandoffRecord, record_handoff_unified`
- Update to use unified recorder

**Expected Impact**: ~200 lines duplication eliminated

---

## Phase 3: Simplify Model Hierarchy (LOW RISK)

### Task 3.1: Rename ReviewAgentOptions to AgentOptions
**File**: `src/vibe3/models/review_runner.py`

**Changes**:
- Rename class: `ReviewAgentOptions` → `AgentOptions`
- Keep frozen dataclass structure
- Add comment: "# Used by all agent commands (plan/run/review)"

### Task 3.2: Remove AgentExecutionRequest/Outcome wrappers
**File**: `src/vibe3/models/agent_execution.py`

**Actions**:
- Delete file entirely (thin wrappers add no value)
- Update imports in `agent_execution_service.py`

### Task 3.3: Simplify agent_execution_service.py
**File**: `src/vibe3/services/agent_execution_service.py`

**Changes**:
- Remove `AgentExecutionRequest` import
- Update signature: `execute_agent(options: AgentOptions, prompt_file_content: str, task: str | None, dry_run: bool, session_id: str | None) -> AgentExecutionOutcome`
- Simplify: directly call `run_review_agent()` with `AgentOptions`

**Expected Impact**: Simpler call chain, no type conversions

---

## Phase 4: Add Handoff UI Module (LOW RISK)

### Task 4.1: Create handoff UI module
**File**: `src/vibe3/ui/handoff_ui.py`

```python
"""Handoff-specific UI rendering."""

from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


def render_handoff_list(branch: str, handoffs: list[dict]) -> None:
    """Render handoff artifacts as a table."""
    table = Table(title=f"Handoff Artifacts: {branch}")
    table.add_column("Time", style="cyan")
    table.add_column("Kind", style="magenta")
    table.add_column("Actor", style="green")
    table.add_column("Detail", style="white")

    for h in handoffs:
        table.add_row(
            h.get("timestamp", ""),
            h.get("kind", ""),
            h.get("actor", ""),
            h.get("detail", "")
        )

    console.print(table)


def render_handoff_detail(artifact_path: Path) -> None:
    """Display handoff artifact content."""
    content = artifact_path.read_text(encoding="utf-8")
    console.print(Panel(content, title=str(artifact_path.name)))


def render_handoff_summary(branch: str, stats: dict) -> None:
    """Show summary statistics for handoffs."""
    console.print(f"\n[bold]Handoff Summary: {branch}[/bold]")
    console.print(f"  Total artifacts: {stats.get('total', 0)}")
    console.print(f"  Plans: {stats.get('plans', 0)}")
    console.print(f"  Runs: {stats.get('runs', 0)}")
    console.print(f"  Reviews: {stats.get('reviews', 0)}")
```

### Task 4.2: Extend handoff command
**File**: `src/vibe3/commands/handoff.py`

**Add commands**:
```python
@app.command()
def list(
    branch: str | None = None,
    kind: str | None = None,
) -> None:
    """List handoff artifacts for current or specified branch."""
    # Implementation using handoff_service queries

@app.command()
def show(artifact: Path) -> None:
    """Display handoff artifact content."""
    from vibe3.ui.handoff_ui import render_handoff_detail
    render_handoff_detail(artifact)
```

**Expected Impact**: Better handoff discoverability and debugging

---

## Verification Steps

After each phase:
1. Run: `uv run pytest tests/vibe3/commands/test_run_command.py tests/vibe3/commands/test_plan_command.py tests/vibe3/commands/test_review_command.py`
2. Run: `uv run mypy src/vibe3`
3. Test: `vibe3 run "test lightweight mode"`
4. Test: `vibe3 plan "test plan"`
5. Test: `vibe3 review --base`
6. Verify: `vibe3 handoff show` shows correct records

---

## Expected Outcomes

**Lines of Code**: ~400-500 lines reduction
**Files Modified**: 15 files
**Files Created**: 4 files
**Files Deleted**: 1 file (agent_execution.py)
**Maintenance**: Adding new options/logic requires 1 change instead of 3
**Consistency**: Unified patterns across all agent commands

---

## Implementation Order

1. Phase 1 (Command options) - LOW RISK
2. Phase 3 (Model simplification) - LOW RISK
3. Phase 2 (Handoff recording) - MEDIUM RISK
4. Phase 4 (Handoff UI) - LOW RISK

Total estimated effort: 2-3 hours