"""Manager configuration helpers with ConventionResolver fallback.

This module provides configuration resolution functions that fallback to
ConventionResolver defaults when explicit config values are not set.
"""

from __future__ import annotations

from vibe3.config.convention_resolver import ConventionResolver
from vibe3.models import OrchestraConfig, SupervisorHandoffConfig


def get_manager_usernames(config: OrchestraConfig) -> tuple[str, ...]:
    """Resolve manager usernames from config with ConventionResolver fallback.

    Env variable overrides (MANAGER_USERNAMES) are applied at config load time
    via apply_env_overrides; callers should use get_config_with_env_override to
    obtain a config that already reflects any env overrides.

    Priority:
    1. Config value (env overrides already applied during config loading)
    2. ConventionResolver default

    Args:
        config: OrchestraConfig instance

    Returns:
        Tuple of manager usernames (e.g., ('vibe-manager-agent',))

    Example:
        >>> config = OrchestraConfig()
        >>> get_manager_usernames(config)
        ('vibe-manager-agent',)
    """
    if config.manager_usernames:
        return config.manager_usernames

    # Fallback to ConventionResolver
    resolver = ConventionResolver.from_repo()
    convention = resolver.resolve()
    return convention.manager_usernames


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

    resolver = ConventionResolver.from_repo()
    convention = resolver.resolve()
    return convention.state_label(convention.handoff_label)
