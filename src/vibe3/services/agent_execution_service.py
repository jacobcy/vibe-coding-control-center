"""Shared execution service for command -> codeagent-wrapper workflows."""

from typing import Literal

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.models.agent_execution import AgentExecutionOutcome, AgentExecutionRequest
from vibe3.services.flow_service import FlowService
from vibe3.services.review_runner import run_review_agent

SessionRole = Literal["planner", "executor", "reviewer"]


def load_session_id(role: SessionRole) -> str | None:
    """Load existing session_id for the current branch and role."""
    branch = "unknown"
    try:
        branch = GitClient().get_current_branch()
        flow_status = FlowService().get_flow_status(branch)
        if not flow_status:
            return None

        role_field = f"{role}_session_id"
        return getattr(flow_status, role_field, None)
    except Exception as exc:
        logger.bind(domain="agent_execution", role=role, branch=branch).warning(
            f"Failed to load session id: {type(exc).__name__}"
        )
        return None


def execute_agent(request: AgentExecutionRequest) -> AgentExecutionOutcome:
    """Execute codeagent-wrapper and resolve effective session id."""
    result = run_review_agent(
        request.prompt_file_content,
        request.options,
        task=request.task,
        dry_run=request.dry_run,
        session_id=request.session_id,
    )
    effective_session_id = result.session_id or request.session_id
    return AgentExecutionOutcome(
        result=result, effective_session_id=effective_session_id
    )
