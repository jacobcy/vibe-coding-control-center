"""Regression tests for migrated repository config paths."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

from vibe3.config.settings import VibeConfig
from vibe3.prompts.manifest import DEFAULT_PROMPT_RECIPES_PATH


def test_migrated_repo_config_duplicates_removed() -> None:
    """Migrated config should not keep root-level duplicate files."""
    removed_paths = [
        "config/settings.yaml",
        "config/loc_limits.yaml",
        "config/prompts.yaml",
        "config/models.json",
        "config/skills.json",
        "config/prompt-recipes.yaml",
        "config/dependencies.toml",
        "config/aliases.sh",
        "config/loader.sh",
    ]

    for path in removed_paths:
        assert not Path(path).exists(), path


def test_prompt_recipes_live_in_prompts_layer() -> None:
    """Prompt recipes belong beside prompt templates, not under config/v3."""
    assert DEFAULT_PROMPT_RECIPES_PATH == Path("config/prompts/prompt-recipes.yaml")
    assert Path("config/prompts/prompt-recipes.yaml").exists()
    assert not Path("config/v3/prompt-recipes.yaml").exists()


def test_settings_does_not_define_prompt_content_fields() -> None:
    """Settings may bind prompt sources, but prompt output lives in prompts config."""
    data = yaml.safe_load(Path("config/v3/settings.yaml").read_text()) or {}
    prompt_content_fields = {
        "agent_prompt": {"global_notice"},
        "review": {"output_format", "review_task", "retry_task", "review_prompt"},
        "plan": {"output_format", "plan_task", "retry_task", "plan_prompt"},
        "run": {
            "output_format",
            "run_task",
            "coding_task",
            "retry_task",
            "run_prompt",
        },
    }

    for section, fields in prompt_content_fields.items():
        section_data = data.get(section, {})
        assert fields.isdisjoint(section_data), section

    orchestra = data.get("orchestra", {})
    assert "include_supervisor_content" not in orchestra.get("assignee_dispatch", {})
    assert "include_supervisor_content" not in orchestra.get("governance", {})


def test_settings_prompt_content_fields_fail_fast(tmp_path: Path) -> None:
    """Do not let settings shadow prompt text from config/prompts/prompts.yaml."""
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(
        """
review:
  output_format: "shadow prompt text"
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="review.output_format"):
        VibeConfig.from_yaml(config_path)


def test_get_defaults_prefers_v3_settings_path(tmp_path: Path, monkeypatch) -> None:
    """VibeConfig defaults should not read the deprecated root settings file."""
    v3_config_dir = tmp_path / "config" / "v3"
    v3_config_dir.mkdir(parents=True)
    (tmp_path / "config" / "settings.yaml").write_text(
        "flow:\n  protected_branches:\n    - legacy-main\n",
        encoding="utf-8",
    )
    (v3_config_dir / "settings.yaml").write_text(
        "flow:\n  protected_branches:\n    - v3-main\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)

    config = VibeConfig.get_defaults()

    assert config.flow.protected_branches == ["v3-main"]


def test_dependencies_loader_reads_v3_path(tmp_path: Path, monkeypatch) -> None:
    """The dependencies helper should not require root config/dependencies.toml."""
    config_dir = tmp_path / "config" / "v3"
    config_dir.mkdir(parents=True)
    (config_dir / "dependencies.toml").write_text(
        """
[tools]
[[tools.required]]
name = "demo"
check = "demo --version"
install = "brew install demo"
description = "Demo tool"
""",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    module_path = (
        Path(__file__).resolve().parents[3] / "scripts/vibe-read-dependencies.py"
    )
    spec = importlib.util.spec_from_file_location("vibe_read_dependencies", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError("Failed to load dependencies helper")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("vibe_read_dependencies", module)
    spec.loader.exec_module(module)

    config = module.load_dependencies()

    assert config["tools"]["required"][0]["name"] == "demo"
