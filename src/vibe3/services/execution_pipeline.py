"""Shared execution pipeline usecase for plan/run/review workflows.

Encapsulates the common orchestration logic for agent execution flows,
removing duplication across command layers and enforcing consistent
session handling, execution, and handoff recording.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal

from loguru import logger
from typer import echo

from vibe3.models.review_runner import AgentOptions, AgentResult
from vibe3.services.agent_execution_service import execute_agent, load_session_id
from vibe3.services.handoff_recorder_unified import (
    HandoffRecord,
    record_handoff_unified,
)

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

    # Build execution context
    log.info("Building execution context")
    prompt_content = request.context_builder()

    # Build agent options
    options = request.options_builder()
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

    return ExecutionResult(
        agent_result=result,
        handoff_file=handoff_file,
        session_id=effective_session_id,
    )
