"""Orchestra helper functions with service dependencies.

DEPRECATED: These functions have been moved to config/manager_config.py
to break circular dependencies. This module re-exports them for backward
compatibility only.

For new code, import directly from config:
    from vibe3.config import (
        get_manager_usernames,
        get_handoff_state_label,
    )
"""

from vibe3.config import get_handoff_state_label, get_manager_usernames

__all__ = ["get_manager_usernames", "get_handoff_state_label"]
