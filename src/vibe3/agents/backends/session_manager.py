"""Session management utilities for codeagent backend.

Pure functions for session ID extraction and resume/retry logic.
"""

from __future__ import annotations

import re
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

# Exit codes indicating resume target is invalid
RESUME_RETRY_EXIT_CODES = frozenset({42})

# Error snippets indicating session resume failed
RESUME_RETRY_ERROR_SNIPPETS = (
    "session not found",
    "invalid session",
    "failed to resume",
    "unable to resume",
    "could not resume",
    "resume error",
)


def extract_session_id(stdout: str) -> str | None:
    """Extract session ID from codeagent-wrapper output.

    Pattern:
        SESSION_ID: 262f0fea-eacb-4223-b842-b5b5097f94e8

    Args:
        stdout: Wrapper stdout output

    Returns:
        Session ID string or None if not found
    """
    if not stdout:
        return None
    match = re.search(r"SESSION_ID:\s*([A-Za-z0-9_-]+)", stdout)
    if not match:
        match = re.search(r'"sessionID":"([A-Za-z0-9_-]+)"', stdout)
    if not match:
        match = re.search(r'\\"sessionID\\":\\"([A-Za-z0-9_-]+)\\"', stdout)
    return match.group(1) if match else None


def should_retry_without_session(
    result: subprocess.CompletedProcess[str],
    *,
    session_id: str | None,
) -> bool:
    """Return True when wrapper failure indicates the resume target is invalid.

    Args:
        result: Subprocess result from codeagent-wrapper
        session_id: Session ID that was attempted to resume

    Returns:
        True if should retry without session, False otherwise
    """
    if not session_id:
        return False
    if result.returncode not in RESUME_RETRY_EXIT_CODES:
        return False

    combined_output = f"{result.stdout}\n{result.stderr}".lower()
    return any(snippet in combined_output for snippet in RESUME_RETRY_ERROR_SNIPPETS)
