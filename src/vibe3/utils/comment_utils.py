"""Comment filtering utilities for identifying human vs automated comments."""

import re
from typing import Any

from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.utils.constants import AUTOMATED_MARKERS, GENERIC_AGENT_MARKER_PATTERN


def is_human_comment(comment: dict[str, Any]) -> bool:
    """Return True if the comment author is a human (not a bot or linear).

    Filters out:
    - Linear bot (linear)
    - GitHub bots (login ends with [bot])
    - Manager bot (configured in orchestra.bot_username or manager_usernames)
    - Automated system comments (identified by [marker] prefix at start of line)

    Markers that indicate automated comments
    (see vibe3.utils.constants.AUTOMATED_MARKERS):
    - [manager]: Manager agent reports
    - [resume]: Task resume operations
    - [plan]: Plan phase completion / scope clarification
    - [run]: Run phase completion / blocker
    - [review]: Review verdict / merge guidance
    - [apply]: Governance apply executor results
    - [orchestra]: Orchestra system messages
    - [handoff]: Handoff operations
    - [governance], [governance suggest], [governance auto-recover],
      [governance apply]: Governance routing
    - [agent], [agent:<role>]: Generic agent fallback markers

    These markers prevent automated systems from interpreting their own
    status reports as new human instructions.
    """
    author = comment.get("author") or {}
    login = str(author.get("login") or "").strip().lower()
    body = str(comment.get("body") or "")

    if not login:
        return True

    # Filter by content: automated markers indicate non-human comments
    # Use regex to match marker at start of line (including whitespace)
    # to avoid false positives in human discussion or quotes.
    if body:
        # Build pattern like: ^\s*(\[manager\]|\[resume\]|...)
        escaped_markers = [re.escape(m) for m in AUTOMATED_MARKERS]
        pattern = r"^\s*(" + "|".join(escaped_markers) + ")"
        if re.match(pattern, body, re.IGNORECASE):
            return False

        # Fallback: generic [agent] / [agent:<role>] pattern
        # Matches markers not in the explicit whitelist
        generic_pattern = r"^\s*" + GENERIC_AGENT_MARKER_PATTERN
        if re.match(generic_pattern, body, re.IGNORECASE):
            return False

    # Filter standard bots
    if login == "linear" or login.endswith("[bot]"):
        return False

    # Filter manager bot (if configured)
    try:
        config = load_orchestra_config()

        # Check bot_username
        if config.bot_username and login == config.bot_username.lower():
            return False

        # Check manager_usernames list
        if config.manager_usernames:
            manager_logins = [u.lower() for u in config.manager_usernames]
            if login in manager_logins:
                return False
    except Exception:
        # Config load failed; continue with standard bot filtering
        pass

    return True
