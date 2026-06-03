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

    # 3. Fallback to ConventionResolver
    from vibe3.services.convention_resolver import ConventionResolver

    resolver = ConventionResolver.from_repo()
    convention = resolver.resolve()
    return convention.manager_usernames
