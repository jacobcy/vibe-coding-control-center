"""Unified execution pipeline for agent workflows.

This module provides a unified interface for executing agents with
automatic artifact persistence and event recording.
"""

from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.models.agent_execution import AgentExecutionRequest
from vibe3.models.review_runner import ReviewAgentOptions
from vibe3.services.agent_execution_service import execute_agent
from vibe3.services.handoff_event_service import (
    create_handoff_artifact,
    persist_handoff_event,
)
from vibe3.services.handoff_service import HandoffService


@dataclass(frozen=True)
class ExecutionRequest:
    """Unified execution request.

    Attributes:
        prompt_content: Prompt content to execute
        options: Agent options (agent/backend/model)
        artifact_prefix: Prefix for artifact file (e.g., "plan", "run")
        event_type: Event type for recording (e.g., "handoff_plan")
        actor: Actor name (e.g., "planner", "executor")
        task: Optional task override
        dry_run: Whether this is a dry run
        session_id: Optional session ID for continuation
        refs: Optional additional references for event
        flow_state_updates: Optional flow state updates
    """

    prompt_content: str
    options: ReviewAgentOptions
    artifact_prefix: str
    event_type: str
    actor: str
    task: str | None = None
    dry_run: bool = False
    session_id: str | None = None
    refs: dict[str, str] | None = None
    flow_state_updates: dict[str, object] | None = None


@dataclass(frozen=True)
class ExecutionResult:
    """Unified execution result.

    Attributes:
        success: Whether execution succeeded
        session_id: Session ID for continuation
        artifact_path: Path to created artifact (if any)
        stdout: Execution output
        stderr: Execution errors
    """

    success: bool
    session_id: str | None
    artifact_path: Path | None
    stdout: str
    stderr: str


class ExecutionPipeline:
    """Unified execution pipeline.

    This class provides a single entry point for:
    1. Agent execution
    2. Artifact persistence
    3. Event recording

    It coordinates between agent execution service, handoff service,
    and git client to provide a unified workflow.
    """

    def __init__(
        self,
        git_client: GitClient | None = None,
        handoff_service: HandoffService | None = None,
    ):
        """Initialize pipeline with dependencies.

        Args:
            git_client: Git client for branch context
            handoff_service: Handoff service for directory management
        """
        self.git_client = git_client or GitClient()
        self.handoff_service = handoff_service or HandoffService()

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute unified pipeline.

        This is the main entry point that coordinates:
        1. Agent execution
        2. Artifact persistence
        3. Event recording

        Args:
            request: Execution request

        Returns:
            Execution result with artifact and session info
        """
        log = logger.bind(
            domain="execution_pipeline",
            actor=request.actor,
            event_type=request.event_type,
        )

        log.info("Starting execution pipeline")

        # Step 1: Execute agent
        agent_request = AgentExecutionRequest(
            prompt_file_content=request.prompt_content,
            options=request.options,
            task=request.task,
            dry_run=request.dry_run,
            session_id=request.session_id,
        )

        outcome = execute_agent(agent_request)

        success = outcome.result.exit_code == 0
        log.info(
            "Agent execution completed",
            success=success,
            session_id=outcome.effective_session_id,
        )

        # Step 2: Persist artifact (if not dry run)
        artifact_path = None
        if not request.dry_run and outcome.result.stdout:
            artifact_result = create_handoff_artifact(
                request.artifact_prefix, outcome.result.stdout
            )
            if artifact_result:
                _, artifact_path = artifact_result
                log.info("Artifact persisted", path=str(artifact_path))

        # Step 3: Record event (always, even on failure)
        if not request.dry_run:
            refs = request.refs or {}
            if artifact_path:
                refs["ref"] = str(artifact_path)
            if outcome.effective_session_id:
                refs["session_id"] = outcome.effective_session_id

            branch = self.git_client.get_current_branch()
            persist_handoff_event(
                branch=branch,
                event_type=request.event_type,
                actor=request.actor,
                detail=f"{request.artifact_prefix.capitalize()} completed",
                refs=refs,
                flow_state_updates=request.flow_state_updates,
            )

            log.info("Event recorded", branch=branch)

        return ExecutionResult(
            success=success,
            session_id=outcome.effective_session_id,
            artifact_path=artifact_path,
            stdout=outcome.result.stdout,
            stderr=outcome.result.stderr,
        )
