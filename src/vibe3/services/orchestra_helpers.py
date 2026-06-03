"""Orchestra helper functions with service dependencies."""

from vibe3.models.orchestra_config import OrchestraConfig, SupervisorHandoffConfig


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
    """Resolve manager usernames with env override support.

    Priority:
    1. Environment variable override (MANAGER_USERNAMES)
    2. Config file (orchestra.manager_usernames)
    3. ConventionResolver default

    Args:
        config: OrchestraConfig instance

    Returns:
        Tuple of manager usernames (e.g., ('vibe-manager-agent',))

    Example:
        >>> config = OrchestraConfig()
        >>> get_manager_usernames(config)
        ('vibe-manager-agent',)
    """
    from vibe3.config.env_override import get_env_override

    # 1. Check env var override first
    env_usernames = get_env_override(
        "MANAGER_USERNAMES",
        converter=lambda s: tuple(s.split(",")),
    )
    if env_usernames is not None:
        # Type narrowing: converter returns tuple[str, ...]
        return env_usernames if isinstance(env_usernames, tuple) else ()

    # 2. Use config file
    if config.manager_usernames:
        return config.manager_usernames

    # 3. Fallback to ConventionResolver
    from vibe3.services.convention_resolver import ConventionResolver

    resolver = ConventionResolver.from_repo()
    convention = resolver.resolve()
    return convention.manager_usernames
