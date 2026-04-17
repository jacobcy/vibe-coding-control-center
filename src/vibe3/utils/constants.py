"""Centralized constants for Vibe3.

This module provides a single source of truth for commonly used constants
to avoid duplication and ensure consistency across the codebase.
"""

from typing import Final

# =============================================================================
# Session / Execution Constants
# =============================================================================

# Timeout for sessions in 'starting' state without tmux session
# Sessions older than this without a tmux session are marked as orphaned
STARTING_TIMEOUT_SECONDS: Final[int] = 60

# =============================================================================
# Codex Runtime Log Filter Constants
# =============================================================================

# Known Codex runtime warnings to filter from async logs
# These are non-critical warnings that clutter the logs
KNOWN_CODEX_STATE_DB_WARNINGS: Final[tuple[str, ...]] = (
    r"failed to open state db at .*migration .*missing in the resolved migrations",
    r"failed to initialize state runtime at .*migration "
    r".*missing in the resolved migrations",
    r"state db discrepancy during "
    r"find_thread_path_by_id_str_in_subdir: falling_back",
)

KNOWN_CODEX_SNAPSHOT_WARNING: Final[str] = (
    r'Failed to delete shell snapshot at ".*": Os \{ code: 2, kind: NotFound, '
    r'message: "No such file or directory" \}'
)

KNOWN_CODEX_ANALYTICS_WARNING: Final[str] = (
    r"analytics_client: events failed with status 403 Forbidden:"
)

# All Codex warnings as a combined tuple for easy iteration
ALL_CODEX_WARNINGS: Final[tuple[str, ...]] = (
    *KNOWN_CODEX_STATE_DB_WARNINGS,
    KNOWN_CODEX_SNAPSHOT_WARNING,
    KNOWN_CODEX_ANALYTICS_WARNING,
)

# =============================================================================
# Worker Roles
# =============================================================================

# NOTE: WORKER_ROLES is defined in vibe3.environment.session_registry
# Import from there to avoid circular dependencies.
# from vibe3.environment.session_registry import WORKER_ROLES

# L3 agent roles (manager/plan/run/review) that must not auto-increment session names
# to prevent multiple physical sessions running for the same task
L3_AGENT_ROLES: Final[frozenset[str]] = frozenset({"manager", "plan", "run", "review"})

# =============================================================================
# Flow Event Types (SQLite store.add_event event_type values)
# =============================================================================

# State change events — always recorded after role execution completes
EVENT_STATE_TRANSITIONED: Final[str] = "state_transitioned"
EVENT_STATE_UNCHANGED: Final[str] = "state_unchanged"

# =============================================================================
# Flow State Ref Fields
# =============================================================================

# Review verdict field name in flow_state and event refs
FIELD_VERDICT: Final[str] = "verdict"

# Known verdict values (observational only — manager decides business logic)
VERDICT_PASS: Final[str] = "PASS"
VERDICT_FAIL: Final[str] = "FAIL"
VERDICT_UNKNOWN: Final[str] = "UNKNOWN"
