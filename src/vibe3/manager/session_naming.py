"""Shared session naming conventions and utilities for manager execution."""

import re
import time
from pathlib import Path
from typing import Literal

from vibe3.agents.backends.codeagent import extract_session_id


def build_session_name(
    role: str,
    target_type: str,
    target_id: str,
) -> str:
    """Unified naming rule: vibe3-{role}-{target_type}-{target_id}."""
    return f"vibe3-{role}-{target_type}-{target_id}"


def get_manager_session_name(issue_number: int) -> str:
    """Return the canonical tmux session name for manager execution.

    This naming convention is the single source of truth for:
    - tmux execution name (manager_executor, run.py)
    - async log naming prefix
    - live-session detection prefix (state_label_dispatch)

    Args:
        issue_number: The GitHub issue number being managed

    Returns:
        Canonical session name: vibe3-manager-issue-{issue_number}
    """
    return f"vibe3-manager-issue-{issue_number}"


def get_trigger_session_prefix(
    trigger_name: Literal["manager", "plan", "run", "review"],
    issue_number: int,
) -> str:
    """Return session prefix for runtime trigger dispatch detection.

    Args:
        trigger_name: The trigger type (manager, plan, run, review)
        issue_number: The GitHub issue number

    Returns:
        Session prefix for tmux list matching: vibe3-{trigger_name}-issue-{issue_number}
    """
    return f"vibe3-{trigger_name}-issue-{issue_number}"


def wait_for_async_session_id(
    log_path: Path, *, timeout_seconds: float = 3.0
) -> str | None:
    """Best-effort poll async output and wrapper log for session id.

    Args:
        log_path: Path to async log file
        timeout_seconds: Maximum time to wait

    Returns:
        Session ID if found, None otherwise
    """
    wrapper_log_path: Path | None = None
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if log_path.exists():
            try:
                repo_log_text = log_path.read_text()
            except OSError:
                repo_log_text = ""
            session_id = extract_session_id(repo_log_text)
            if session_id:
                return session_id

            if wrapper_log_path is None:
                match = re.search(
                    r"Log:\s*(\S+codeagent-wrapper-\d+\.log)",
                    repo_log_text,
                )
                if match:
                    wrapper_log_path = Path(match.group(1))

        if wrapper_log_path and wrapper_log_path.exists():
            try:
                wrapper_log_text = wrapper_log_path.read_text()
            except OSError:
                wrapper_log_text = ""
            session_id = extract_session_id(wrapper_log_text)
            if session_id:
                return session_id
        time.sleep(0.1)
    return None
