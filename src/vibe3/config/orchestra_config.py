"""Orchestra configuration - re-exports and helper functions.

This module provides:
1. Re-exports of Pydantic models from models.orchestra_config (backward compatibility)
2. Standalone helper functions for resolving config values with service dependencies
"""

from vibe3.models.orchestra_config import (
    AssigneeDispatchConfig,
    CircuitBreakerConfig,
    GovernanceConfig,
    OrchestraConfig,
    PeriodicCheckConfig,
    PollingConfig,
    PRReviewDispatchConfig,
    StateLabelDispatchConfig,
    SupervisorHandoffConfig,
    _default_pid_file,
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
    "_default_pid_file",
    "get_handoff_state_label",
    "get_manager_usernames",
]


def get_handoff_state_label(config: SupervisorHandoffConfig) -> str:
    """Resolve handoff state label with fallback to ConventionResolver.

    Args:
        config: SupervisorHandoffConfig instance

    Returns:
        Handoff state label (e.g., 'state/handoff').

    Example:
        >>> config = SupervisorHandoffConfig()
        >>> get_handoff_state_label(config)
        'state/handoff'
    """
    if config.handoff_state_label:
        return config.handoff_state_label
    from vibe3.services.convention_resolver import ConventionResolver

    resolver = ConventionResolver.from_repo()
    convention = resolver.resolve()
    return convention.state_label(convention.handoff_label)


def get_manager_usernames(config: OrchestraConfig) -> tuple[str, ...]:
    """Resolve manager usernames with fallback to ConventionResolver.

    Args:
        config: OrchestraConfig instance

    Returns:
        Tuple of manager usernames (e.g., ('vibe-manager-agent',)).

    Example:
        >>> config = OrchestraConfig()
        >>> get_manager_usernames(config)
        ('vibe-manager-agent',)
    """
    if config.manager_usernames:
        return config.manager_usernames
    from vibe3.services.convention_resolver import ConventionResolver

    resolver = ConventionResolver.from_repo()
    convention = resolver.resolve()
    return convention.manager_usernames
