"""Shared execution service for command -> codeagent-wrapper workflows.

Migrated from vibe3.services.agent_execution_service.
"""

import re
from typing import Literal

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.exceptions import SystemError, UserError
from vibe3.services.session_registry import SessionRegistryService

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
    """Load existing session_id for the current branch and role from registry.

    Returns None for stale or malformed values so callers can open a fresh
    session instead of passing an invalid resume target to codeagent-wrapper.

    The legacy flow_state fields (manager_session_id, planner_session_id, etc.)
    are no longer read. The runtime_session registry is the single source of truth.
    """
    resolved_branch = branch or "unknown"
    try:
        resolved_branch = branch or GitClient().get_current_branch()
        registry = SessionRegistryService(
            store=SQLiteClient(),
            backend=None,  # backend only needed for liveness checks
        )
        sessions = registry.get_truly_live_sessions_for_branch(resolved_branch)

        # Find session matching role with valid backend_session_id
        for session in sessions:
            if session.get("role") != role:
                continue
            backend_session_id = session.get("backend_session_id")
            if not backend_session_id:
                continue
            if not isinstance(backend_session_id, str):
                continue
            if not _is_valid_session_id(backend_session_id):
                logger.bind(
                    domain="agent_execution", role=role, branch=resolved_branch
                ).warning(
                    f"Registry backend_session_id '{backend_session_id}' is not a "
                    "valid wrapper session id; ignoring it and starting fresh."
                )
                continue
            return backend_session_id

        return None
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
