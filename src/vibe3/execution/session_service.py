"""Execution session resume helpers."""

import re
from typing import Literal

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.environment.session_registry import SessionRegistryService
from vibe3.exceptions import SystemError, UserError

SessionRole = Literal[
    "manager", "planner", "executor", "reviewer", "supervisor", "governance"
]

_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _is_valid_session_id(value: str) -> bool:
    """Return True for wrapper-like session ids, but reject tmux session names."""
    if not _SESSION_ID_RE.match(value):
        return False
    return not value.startswith("vibe3-")


def load_session_id(role: SessionRole, branch: str | None = None) -> str | None:
    """Load existing session_id for the current branch and role from registry."""
    resolved_branch = branch or "unknown"
    try:
        resolved_branch = branch or GitClient().get_current_branch()
        registry = SessionRegistryService(
            store=SQLiteClient(),
            backend=None,
        )
        sessions = registry.get_truly_live_sessions_for_branch(resolved_branch)

        for session in sessions:
            if session.get("role") != role:
                continue
            backend_session_id = session.get("backend_session_id")
            if not backend_session_id or not isinstance(backend_session_id, str):
                continue
            if not _is_valid_session_id(backend_session_id):
                logger.bind(
                    domain="agent_execution", role=role, branch=resolved_branch
                ).warning(
                    f"Registry backend_session_id '{backend_session_id}' is not a "
                    "valid wrapper session id; ignoring it and starting fresh."
                )
                continue
            return str(backend_session_id)

        return None
    except (UserError, SystemError) as exc:
        logger.bind(domain="agent_execution", role=role, branch=resolved_branch).debug(
            f"No session to resume: {exc}"
        )
        return None
    except Exception as exc:
        logger.bind(
            domain="agent_execution", role=role, branch=resolved_branch
        ).warning(f"Unexpected error loading session: {type(exc).__name__}: {exc}")
        return None
