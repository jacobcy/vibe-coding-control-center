"""Orchestra configuration (backward compatibility layer).

All configuration classes have been moved to models/orchestra_config.py to avoid
circular dependencies. This module only re-exports them for backward compatibility.
"""

# Re-export all configuration classes from models layer
from vibe3.models.orchestra_config import (
    AssigneeDispatchConfig,
    CircuitBreakerConfig,
    CommentReplyConfig,
    GovernanceConfig,
    OrchestraConfig,
    PollingConfig,
    PRReviewDispatchConfig,
    StateLabelDispatchConfig,
    SupervisorHandoffConfig,
)

__all__ = [
    "OrchestraConfig",
    "PollingConfig",
    "AssigneeDispatchConfig",
    "CommentReplyConfig",
    "PRReviewDispatchConfig",
    "StateLabelDispatchConfig",
    "CircuitBreakerConfig",
    "GovernanceConfig",
    "SupervisorHandoffConfig",
]
