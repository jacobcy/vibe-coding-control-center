"""Orchestra configuration models - re-exported from config layer.

These configuration classes are shared across orchestra, manager, and agents
modules. Moved to config layer to fix architecture violation (config should
not depend on models).

This module re-exports for backwards compatibility.
"""

from vibe3.config.orchestra_config import (
    AssigneeDispatchConfig,
    CircuitBreakerConfig,
    CommentReplyConfig,
    GovernanceConfig,
    OrchestraConfig,
    PollingConfig,
    PRReviewDispatchConfig,
    StateLabelDispatchConfig,
    SupervisorHandoffConfig,
    WorktreeCleanupConfig,
    _default_pid_file,
)

__all__ = [
    "AssigneeDispatchConfig",
    "CircuitBreakerConfig",
    "CommentReplyConfig",
    "GovernanceConfig",
    "OrchestraConfig",
    "PollingConfig",
    "PRReviewDispatchConfig",
    "StateLabelDispatchConfig",
    "SupervisorHandoffConfig",
    "WorktreeCleanupConfig",
    "_default_pid_file",
]
