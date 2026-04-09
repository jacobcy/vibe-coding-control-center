"""Tests for orchestra config mapping."""

from unittest.mock import patch

from vibe3.config.settings import VibeConfig
from vibe3.models.orchestra_config import OrchestraConfig


def test_from_settings_maps_supervisor_prompt_template() -> None:
    settings = VibeConfig.get_defaults()
    settings.orchestra.supervisor_handoff.prompt_template = "orchestra.supervisor.apply"

    with patch("vibe3.config.settings.VibeConfig.get_defaults", return_value=settings):
        config = OrchestraConfig.from_settings()

    assert config.supervisor_handoff.prompt_template == "orchestra.supervisor.apply"
