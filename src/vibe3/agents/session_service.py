"""Shared execution service for command -> codeagent-wrapper workflows.

Migrated from vibe3.services.agent_execution_service.
"""

from typing import Literal

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.exceptions import SystemError, UserError
from vibe3.services.flow_service import FlowService

SessionRole = Literal["manager", "planner", "executor", "reviewer"]


def load_session_id(role: SessionRole, branch: str | None = None) -> str | None:
    """Load existing session_id for the current branch and role."""
    resolved_branch = branch or "unknown"
    try:
        resolved_branch = branch or GitClient().get_current_branch()
        flow_status = FlowService().get_flow_status(resolved_branch)
        if not flow_status:
            return None

        role_field = f"{role}_session_id"
        return getattr(flow_status, role_field, None)
    except (UserError, SystemError) as exc:
        # Expected: no flow exists or flow not initialized
        logger.bind(domain="agent_execution", role=role, branch=resolved_branch).debug(
            f"No session to resume: {exc}"
        )
        return None
    except Exception as exc:
        # Unexpected: log warning but don't fail
        logger.bind(
            domain="agent_execution", role=role, branch=resolved_branch
        ).warning(f"Unexpected error loading session: {type(exc).__name__}: {exc}")
        return None
