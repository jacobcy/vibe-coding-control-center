"""Helpers for loading orchestra config from root settings."""

from __future__ import annotations

from vibe3.config.orchestra_config import OrchestraConfig


def load_orchestra_config() -> OrchestraConfig:
    """Load orchestra config with env overrides applied.

    Uses get_config_with_env_override so that keys.env and OVERRIDE_RULES
    are respected (e.g. MANAGER_USERNAMES overrides orchestra.manager_usernames).
    """
    from vibe3.config.loader import get_config_with_env_override

    config = get_config_with_env_override()
    return config.orchestra.model_copy(deep=True)
