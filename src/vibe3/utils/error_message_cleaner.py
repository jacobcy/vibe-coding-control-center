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
