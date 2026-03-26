"""Shared execution service for command -> codeagent-wrapper workflows."""

from typing import Literal

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.exceptions import SystemError, UserError
from vibe3.models.review_runner import AgentOptions, AgentResult
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
    except (UserError, SystemError) as exc:
        # Expected: no flow exists or flow not initialized
        logger.bind(domain="agent_execution", role=role, branch=branch).debug(
            f"No session to resume: {exc}"
        )
        return None
    except Exception as exc:
        # Unexpected: log warning but don't fail
        logger.bind(domain="agent_execution", role=role, branch=branch).warning(
            f"Unexpected error loading session: {type(exc).__name__}: {exc}"
        )
        return None


def execute_agent(
    options: AgentOptions,
    prompt_file_content: str,
    task: str | None = None,
    dry_run: bool = False,
    session_id: str | None = None,
) -> AgentResult:
    """Execute codeagent-wrapper using direct parameters.

    The caller is responsible for resolving the effective session id via
    ``result.session_id or session_id`` when continuation semantics matter.
    """
    return run_review_agent(
        prompt_file_content,
        options,
        task=task,
        dry_run=dry_run,
        session_id=session_id,
    )
