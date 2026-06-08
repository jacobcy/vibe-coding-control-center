"""Orchestra configuration - re-exports and helper functions.

This module provides:
1. Re-exports of Pydantic models from models.orchestra_config (backward compatibility)
2. Standalone helper functions for resolving config values with service dependencies
"""

from vibe3.models import (
    AssigneeDispatchConfig,
    CircuitBreakerConfig,
    GovernanceConfig,
    OrchestraConfig,
    PeriodicCheckConfig,
    PollingConfig,
    PRReviewDispatchConfig,
    StateLabelDispatchConfig,
    SupervisorHandoffConfig,
    default_pid_file,
)

__all__ = [
    "AssigneeDispatchConfig",
    "CircuitBreakerConfig",
    "GovernanceConfig",
    "OrchestraConfig",
    "PeriodicCheckConfig",
    "PollingConfig",
    "PRReviewDispatchConfig",
    "StateLabelDispatchConfig",
    "SupervisorHandoffConfig",
    "default_pid_file",
]
