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


def test_supplementary_loading_from_external_cwd(tmp_path: Path, monkeypatch) -> None:
    """Verify that supplementary data is loaded when CWD is external."""
    from vibe3.config.settings import VibeConfig

    monkeypatch.chdir(tmp_path)
    config = VibeConfig.get_defaults()
    # Verify supplementary fields are populated
    assert config.doc_limits, "doc_limits should be loaded from loc_limits.yaml"
    assert config.review.review_task, "review_task should be loaded from prompts.yaml"
    assert config.plan.plan_task, "plan_task should be loaded from prompts.yaml"
