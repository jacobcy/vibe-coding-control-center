"""Tests for .vibe/config.yaml validity."""

from pathlib import Path

import yaml


def test_vibe_center_repo_config():
    """Test that current repo has valid .vibe/config.yaml."""
    config_path = Path(__file__).parents[3] / ".vibe/config.yaml"
    assert config_path.exists(), ".vibe/config.yaml must exist in repo root"

    with config_path.open() as f:
        config = yaml.safe_load(f)

    assert config["profile"] == "vibe-center"
    assert config["adapter"] == "vibe-center"
