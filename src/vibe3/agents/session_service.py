"""Shared execution service for command -> codeagent-wrapper workflows.

Migrated from vibe3.services.agent_execution_service.
"""

import re
from typing import Literal

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.exceptions import SystemError, UserError
from vibe3.services.flow_service import FlowService

SessionRole = Literal["manager", "planner", "executor", "reviewer"]

_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _is_valid_session_id(value: str) -> bool:
    """Return True for wrapper-like session ids, but reject tmux session names.

    Wrapper sessions in this repo currently appear as UUIDs, `ses_...`, or
    `sess-...`. Tmux sessions for async workers use the `vibe3-...` naming
    scheme and must not be passed to wrapper resume.
    """
    if not _SESSION_ID_RE.match(value):
        return False
    return not value.startswith("vibe3-")


def load_session_id(role: SessionRole, branch: str | None = None) -> str | None:
    """Load existing session_id for the current branch and role.

    Returns None for stale or malformed values so callers can open a fresh
    session instead of passing an invalid resume target to codeagent-wrapper.
    """
    resolved_branch = branch or "unknown"
    try:
        resolved_branch = branch or GitClient().get_current_branch()
        flow_status = FlowService().get_flow_status(resolved_branch)
        if not flow_status:
            return None

        role_field = f"{role}_session_id"
        raw = getattr(flow_status, role_field, None)
        if not isinstance(raw, str) or not raw:
            return None

        if not _is_valid_session_id(raw):
            logger.bind(
                domain="agent_execution", role=role, branch=resolved_branch
            ).warning(
                f"Stored {role_field} '{raw}' is not a valid wrapper session id; "
                "ignoring it and starting a fresh session instead."
            )
            return None

        return raw
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
