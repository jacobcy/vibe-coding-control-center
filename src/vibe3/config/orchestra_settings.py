"""Helpers for loading orchestra config from root settings."""

from __future__ import annotations

from pathlib import Path

from vibe3.config.orchestra_config import OrchestraConfig


def load_orchestra_config(*, target_repo: Path | None = None) -> OrchestraConfig:
    """Load orchestra config with env overrides applied.

    Uses get_config_with_env_override so that keys.env and OVERRIDE_RULES
    are respected (e.g. MANAGER_USERNAMES overrides orchestra.manager_usernames).

    Args:
        target_repo: Optional target repository path for project config resolution.
    """
    from vibe3.config.loader import get_config_with_env_override, load_config

    config = get_config_with_env_override(load_config(target_repo=target_repo))
    return config.orchestra.model_copy(deep=True)
