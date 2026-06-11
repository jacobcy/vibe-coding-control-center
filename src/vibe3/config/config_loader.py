"""Config loading utilities for non-CLI contexts (domain handlers, etc).

These functions provide config loading without typer dependencies,
allowing lower layers (domain, services) to load config without
violating layer architecture (no upward imports).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vibe3.config import VibeConfig


def load_config_for_role(
    role: str,
    agent: str | None,
    backend: str | None,
    model: str | None,
) -> "VibeConfig":
    """Load runtime config for a role without CLI dependencies.

    This is a non-typer version of load_config_and_validate_model
    for use in domain handlers and other non-CLI contexts.

    Args:
        role: Role name (run/plan/review)
        agent: CLI --agent value
        backend: CLI --backend value
        model: CLI --model value

    Returns:
        Loaded VibeConfig

    Raises:
        ConfigError: If config loading fails
        ValueError: If --model used without backend
    """
    from vibe3.config import build_role_cli_overrides, load_runtime_config
    from vibe3.exceptions import ConfigError

    # Validate model requires backend
    cli_overrides = build_role_cli_overrides(role, agent, backend, model)
    if cli_overrides and cli_overrides.model:
        config_backend = backend  # CLI backend takes precedence
        if not config_backend:
            raise ValueError(
                f"--model requires --backend to be specified "
                f"(role={role}, model={cli_overrides.model})"
            )

    try:
        config = load_runtime_config(cli_overrides=cli_overrides or None)
    except ConfigError as e:
        raise ConfigError(f"Configuration error for role {role}: {e}") from e

    return config
