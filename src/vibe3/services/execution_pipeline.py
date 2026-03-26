"""Shared execution pipeline usecase for plan/run/review workflows.

Encapsulates the common orchestration logic for agent execution flows,
removing duplication across command layers and enforcing consistent
session handling, execution, and handoff recording.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Literal

from loguru import logger
from typer import echo

from vibe3.clients.git_client import GitClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.models.review_runner import AgentOptions, AgentResult
from vibe3.services.agent_execution_service import execute_agent, load_session_id
from vibe3.services.handoff_recorder_unified import (
    HandoffRecord,
    record_handoff_unified,
)
from vibe3.services.review_runner import format_agent_actor

SessionRole = Literal["planner", "executor", "reviewer"]


@dataclass
class ExecutionRequest:
    """Request payload for execution pipeline."""

    role: SessionRole
    context_builder: Callable[[], str]
    options_builder: Callable[[], AgentOptions]
    task: str | None = None
    dry_run: bool = False
    handoff_kind: str = "run"
    handoff_metadata: dict[str, Any] | None = None


@dataclass
class ExecutionResult:
    """Result of execution pipeline."""

    agent_result: AgentResult
    handoff_file: Path | None
    session_id: str | None


def _run_lifecycle_enabled(request: ExecutionRequest) -> bool:
    return request.role == "executor" and request.handoff_kind == "run"


def _get_current_branch() -> str | None:
    try:
        return GitClient().get_current_branch()
    except Exception as exc:  # pragma: no cover - defensive path
        logger.bind(domain="execution_pipeline").warning(
            f"Failed to resolve branch for run lifecycle event: {exc}"
        )
        return None


def _persist_run_lifecycle_event(
    branch: str | None,
    actor: str,
    event_type: Literal["run_started", "run_completed", "run_aborted"],
    detail: str,
    session_id: str | None = None,
    refs: dict[str, str] | None = None,
) -> None:
    if branch is None:
        return

    now = datetime.now().isoformat()
    flow_state_updates: dict[str, object] = {
        "executor_actor": actor,
    }
    if session_id:
        flow_state_updates["executor_session_id"] = session_id

    if event_type == "run_started":
        flow_state_updates.update(
            executor_status="running",
            execution_started_at=now,
            execution_completed_at=None,
        )
    elif event_type == "run_completed":
        flow_state_updates.update(
            executor_status="done",
            execution_completed_at=now,
            execution_pid=None,
        )
    else:
        flow_state_updates.update(
            executor_status="crashed",
            execution_completed_at=now,
            execution_pid=None,
        )

    store = SQLiteClient()
    store.update_flow_state(branch, **flow_state_updates)
    store.add_event(branch, event_type, actor, detail=detail, refs=refs)


def run_execution_pipeline(request: ExecutionRequest) -> ExecutionResult:
    """Run the full agent execution pipeline.

    Handles:
    1. Session ID loading
    2. Context building
    3. Agent execution
    4. Handoff recording (if not dry_run)

    Args:
        request: Execution configuration

    Returns:
        ExecutionResult with agent output, handoff path, and effective session ID
    """
    log = logger.bind(
        domain="execution_pipeline",
        role=request.role,
        handoff_kind=request.handoff_kind,
    )

    # Load existing session
    session_id = load_session_id(request.role)
    log.debug("Loaded session", session_id=session_id)

    # Build agent options early so the start event can record the actual actor.
    options = request.options_builder()
    actor = format_agent_actor(options)
    branch = (
        _get_current_branch()
        if not request.dry_run and _run_lifecycle_enabled(request)
        else None
    )

    if branch:
        _persist_run_lifecycle_event(
            branch,
            actor,
            "run_started",
            "Run started (status: in_progress)",
            session_id=session_id,
        )

    # Build execution context
    log.info("Building execution context")
    try:
        prompt_content = request.context_builder()

        log.info(
            "Running agent",
            agent=options.agent,
            backend=options.backend,
            model=options.model,
            session_id=session_id,
        )
        echo(f"-> Executing with {options.agent or options.backend}...")

        # Execute agent
        result = execute_agent(
            options,
            prompt_content,
            task=request.task,
            dry_run=request.dry_run,
            session_id=session_id,
        )

        if request.dry_run:
            return ExecutionResult(
                agent_result=result,
                handoff_file=None,
                session_id=result.session_id or session_id,
            )

        # Record handoff
        effective_session_id = result.session_id or session_id
        handoff_file = record_handoff_unified(
            HandoffRecord(
                kind=request.handoff_kind,  # type: ignore[arg-type]
                content=result.stdout,
                options=options,
                session_id=effective_session_id,
                metadata=request.handoff_metadata,
            )
        )
        if handoff_file:
            echo(f"-> {request.handoff_kind.capitalize()} saved: {handoff_file}")

        if branch:
            refs = {"status": "completed"}
            if handoff_file:
                refs["ref"] = str(handoff_file)
            _persist_run_lifecycle_event(
                branch,
                actor,
                "run_completed",
                "Run completed (status: completed)",
                session_id=effective_session_id,
                refs=refs,
            )

        return ExecutionResult(
            agent_result=result,
            handoff_file=handoff_file,
            session_id=effective_session_id,
        )
    except BaseException as exc:
        if branch:
            _persist_run_lifecycle_event(
                branch,
                actor,
                "run_aborted",
                f"Run aborted (status: aborted, reason: {exc})",
                session_id=session_id,
                refs={"reason": str(exc), "status": "aborted"},
            )
        raise
