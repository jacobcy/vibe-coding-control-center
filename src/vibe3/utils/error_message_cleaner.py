"""Shared error message cleaning utilities.

Provides precompiled regex patterns and a single clean_error_message()
function that extracts duplicated cleaning logic from status_render.py
and serve_status_service.py.
"""

from __future__ import annotations

import re

# Precompiled regex patterns for shared cleaning steps
_TMPDIR_RE = re.compile(r"\s*CLAUDE_CODE_TMPDIR:")
_RECENT_ERRORS_RE = re.compile(r"\s*\|\s*=== Recent Errors ===")
_TRAILING_PIPE_RE = re.compile(r"\s*\|\s*$")

# Precompiled constant for codeagent-wrapper prefix (used by callers before delegation)
# Note: ^ anchor ensures this only matches at line start (for backward compatibility)
CODEAGENT_WRAPPER_RE = re.compile(r"^codeagent-wrapper failed \(code \d+\):\s*")

# Non-anchored version for removing prefix anywhere in the line
CODEAGENT_WRAPPER_ANYWHERE_RE = re.compile(r"codeagent-wrapper failed \(code \d+\):\s*")


def clean_error_message(message: str) -> str:
    """Remove common noise patterns from error messages.

    Applies three cleaning steps in order:
    1. Remove CLAUDE_CODE_TMPDIR and everything after it
    2. Remove ' | === Recent Errors ===' suffix
    3. Remove trailing pipe separators

    Args:
        message: Error message after any caller-specific prefix removal

    Returns:
        Cleaned error message
    """
    cleaned = _TMPDIR_RE.split(message)[0].strip()
    cleaned = _RECENT_ERRORS_RE.split(cleaned)[0].strip()
    cleaned = _TRAILING_PIPE_RE.sub("", cleaned).strip()
    return cleaned


def compute_blocked_reason_summary(blocked_reason: str) -> str:
    """Compute a display-ready summary from a raw blocked_reason string.

    Strips wrapper prefixes, removes TMPDIR/RecentErrors noise,
    truncates at sentence boundary if needed.

    Args:
        blocked_reason: Raw blocked_reason string (may contain multiple lines)

    Returns:
        Cleaned, truncated summary suitable for display
    """
    if not blocked_reason:
        return ""

    lines = blocked_reason.strip().split("\n")
    if not lines:
        return ""

    first_line = CODEAGENT_WRAPPER_ANYWHERE_RE.sub("", lines[0].strip())

    if (not first_line or first_line.rstrip(":").startswith("E_")) and len(lines) > 1:
        next_line = lines[1].strip()
        if next_line:
            first_line = next_line

    if len(first_line) <= 60 and "CLAUDE_CODE_TMPDIR" not in first_line:
        result = first_line
    else:
        cleaned = clean_error_message(first_line)
        if len(cleaned) <= 80:
            result = cleaned
        else:
            for sep in ["。", "."]:
                pos = cleaned.rfind(sep, 0, 80)
                if pos > 0:
                    result = cleaned[: pos + 1]
                    break
            else:
                result = cleaned[:80]

    if result.endswith(":"):
        result = result[:-1]

    return result
