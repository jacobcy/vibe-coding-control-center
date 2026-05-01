"""Helpers for loading orchestra config from root settings."""

from __future__ import annotations

from vibe3.config.orchestra_config import OrchestraConfig
from vibe3.config.settings import VibeConfig


def load_orchestra_config() -> OrchestraConfig:
    """Load orchestra config from config/settings.yaml."""
    settings = VibeConfig.get_defaults()
    return settings.orchestra.model_copy(deep=True)
