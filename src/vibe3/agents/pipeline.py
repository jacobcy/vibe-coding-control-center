"""Shared execution pipeline usecase for plan/run/review workflows.

Encapsulates the common orchestration logic for agent execution flows,
removing duplication across command layers and enforcing consistent
session handling, execution, and handoff recording.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from loguru import logger
from typer import echo

from vibe3.agents.base import AgentBackend
from vibe3.agents.review_runner import format_agent_actor
from vibe3.agents.session_service import load_session_id
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.models.review_runner import AgentOptions, AgentResult
from vibe3.services.execution_lifecycle import (
    ExecutionRole,
    persist_execution_lifecycle_event,
)
from vibe3.services.handoff_recorder_unified import (
    HandoffRecord,
    record_handoff_unified,
)


@dataclass
class ExecutionRequest:
    """Request payload for execution pipeline."""

    role: ExecutionRole
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


def run_execution_pipeline(
    request: ExecutionRequest,
    backend: AgentBackend | None = None,
) -> ExecutionResult:
    """Run the full agent execution pipeline.

    Handles:
    1. Session ID loading
    2. Context building
    3. Agent execution
    4. Handoff recording (if not dry_run)

    Args:
        request: Execution configuration
        backend: 可选的 agent 执行后端（默认为 CodeagentBackend）

    Returns:
        ExecutionResult with agent output, handoff path, and effective session ID
    """
    if backend is None:
        from vibe3.agents.backends.codeagent import CodeagentBackend

        backend = CodeagentBackend()

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

    # When running as an async child, the parent process owns lifecycle events.
    # Skip recording to avoid duplicate started/completed/aborted entries.
    _is_async_child = os.environ.get("VIBE3_ASYNC_CHILD") == "1"

    branch = None
    store = None
    if (
        not request.dry_run
        and request.role == "executor"
        and request.handoff_kind == "run"
        and not _is_async_child
    ):
        from vibe3.clients.git_client import GitClient

        try:
            branch = GitClient().get_current_branch()
            store = SQLiteClient()
        except Exception as exc:  # pragma: no cover - defensive path
            logger.bind(domain="execution_pipeline").warning(
                f"Failed to resolve branch for run lifecycle event: {exc}"
            )

    if branch and store:
        persist_execution_lifecycle_event(
            store,
            branch,
            request.role,
            "started",
            actor,
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
        result = backend.run(
            prompt=prompt_content,
            options=options,
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

        if branch and store:
            persist_execution_lifecycle_event(
                store,
                branch,
                request.role,
                "completed",
                actor,
                "Run completed (status: completed)",
                session_id=effective_session_id,
                refs={"status": "completed"},
            )

        return ExecutionResult(
            agent_result=result,
            handoff_file=handoff_file,
            session_id=effective_session_id,
        )
    except BaseException as exc:
        if branch and store:
            persist_execution_lifecycle_event(
                store,
                branch,
                request.role,
                "aborted",
                actor,
                f"Run aborted (status: aborted, reason: {exc})",
                session_id=session_id,
                refs={"reason": str(exc), "status": "aborted"},
            )
        raise
