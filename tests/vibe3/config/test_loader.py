"""Tests for configuration loaders in vibe3.config.loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from vibe3.config.loader import (
    _deep_merge,
    _expand_variables,
    load_config,
    load_runtime_config,
    load_yaml_config,
)
from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.config.settings import VibeConfig
from vibe3.exceptions import ConfigError


class TestExpandVariables:
    """Smoke tests: _expand_variables delegates to expand_config_variables."""

    def test_expand_variables_simple(self) -> None:
        config = {"paths": {"root": "/app"}, "file": "${paths.root}/data"}
        result = _expand_variables(config)
        assert result["file"] == "/app/data"

    def test_expand_variables_with_context(self) -> None:
        config = {"val": "${external.key}"}
        context = {"external": {"key": "resolved"}}
        result = _expand_variables(config, context=context)
        assert result["val"] == "resolved"


class TestDeepMerge:
    """Tests for _deep_merge pure function."""

    def test_deep_merge_override_scalar(self) -> None:
        result = _deep_merge({"a": 1}, {"a": 10})
        assert result == {"a": 10}

    def test_deep_merge_nested_dict(self) -> None:
        base = {"a": {"b": 1, "c": 2}}
        override = {"a": {"c": 3}}
        result = _deep_merge(base, override)
        assert result == {"a": {"b": 1, "c": 3}}

    def test_deep_merge_base_only_keys(self) -> None:
        result = _deep_merge({"a": 1, "b": 2}, {"a": 10})
        assert result == {"a": 10, "b": 2}

    def test_deep_merge_override_only_keys(self) -> None:
        result = _deep_merge({"a": 1}, {"b": 2})
        assert result == {"a": 1, "b": 2}

    def test_deep_merge_three_layers(self) -> None:
        """Three sequential merges respect layer priority."""
        base = {"level": 1, "shared": "base", "nested": {"x": 1, "y": 1}}
        mid = _deep_merge(base, {"level": 2, "shared": "mid", "nested": {"y": 2}})
        final = _deep_merge(mid, {"level": 3, "shared": "top", "nested": {"z": 3}})
        assert final["level"] == 3
        assert final["shared"] == "top"
        assert final["nested"] == {"x": 1, "y": 2, "z": 3}


class TestLoadYamlConfig:
    """Tests for load_yaml_config I/O function."""

    def test_load_yaml_config_file_not_found(self, tmp_path: Path) -> None:
        result = load_yaml_config(tmp_path / "nonexistent.yaml")
        assert result == {}

    def test_load_yaml_config_valid(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text("key: value\nnested:\n  a: 1\n", encoding="utf-8")
        result = load_yaml_config(config_file)
        assert result == {"key": "value", "nested": {"a": 1}}

    def test_load_yaml_config_invalid_non_strict(self, tmp_path: Path) -> None:
        config_file = tmp_path / "bad.yaml"
        config_file.write_text(": [invalid yaml", encoding="utf-8")
        result = load_yaml_config(config_file, strict=False)
        assert result == {}

    def test_load_yaml_config_invalid_strict(self, tmp_path: Path) -> None:
        config_file = tmp_path / "bad.yaml"
        config_file.write_text(": [invalid yaml", encoding="utf-8")
        with pytest.raises(ConfigError, match="Invalid YAML"):
            load_yaml_config(config_file, strict=True)

    def test_load_yaml_config_empty_file(self, tmp_path: Path) -> None:
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("", encoding="utf-8")
        result = load_yaml_config(config_file)
        assert result == {}

    def test_load_yaml_config_non_dict(self, tmp_path: Path) -> None:
        """YAML that parses to a list should return empty dict."""
        config_file = tmp_path / "list.yaml"
        config_file.write_text("- item1\n- item2\n", encoding="utf-8")
        result = load_yaml_config(config_file)
        assert result == {}


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_config_explicit_path(self, tmp_path: Path, monkeypatch) -> None:
        """Provide config_path directly — config loaded from that file."""
        config_file = tmp_path / "explicit.yaml"
        config_file.write_text(
            "flow:\n  protected_branches:\n    - custom-branch\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

        config = load_config(config_path=config_file)
        assert config.flow.protected_branches == ["custom-branch"]

    def test_load_config_three_layer_merge(self, tmp_path: Path, monkeypatch) -> None:
        """Repo → global → project layers merge; project wins."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

        # Repo base config (config/v3/settings.yaml)
        repo_config = tmp_path / "config" / "v3"
        repo_config.mkdir(parents=True)
        (repo_config / "settings.yaml").write_text(
            "flow:\n  protected_branches:\n    - repo-main\n",
            encoding="utf-8",
        )

        # Global config (~/.vibe/settings.yaml)
        global_config = tmp_path / "home" / ".vibe"
        global_config.mkdir(parents=True)
        (global_config / "settings.yaml").write_text(
            "flow:\n  protected_branches:\n    - global-main\n",
            encoding="utf-8",
        )

        # Project config (.vibe/settings.yaml)
        project_config = tmp_path / ".vibe"
        project_config.mkdir(parents=True)
        (project_config / "settings.yaml").write_text(
            "flow:\n  protected_branches:\n    - project-main\n",
            encoding="utf-8",
        )

        config = load_config()
        # Project config is highest priority
        assert config.flow.protected_branches == ["project-main"]

    def test_load_config_missing_returns_defaults(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """No config files found — returns VibeConfig.get_defaults()."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

        config = load_config()
        defaults = VibeConfig.get_defaults()
        # Both should have the same default protected_branches
        assert config.flow.protected_branches == defaults.flow.protected_branches

    def test_load_config_invalid_file_raises(self, tmp_path: Path, monkeypatch) -> None:
        """Global config layer with invalid YAML raises ConfigError (strict=True)."""
        monkeypatch.chdir(tmp_path)

        # Create a valid base config so find_config_file returns something
        repo_config = tmp_path / "config" / "v3"
        repo_config.mkdir(parents=True)
        (repo_config / "settings.yaml").write_text(
            "flow:\n  protected_branches:\n    - repo-main\n",
            encoding="utf-8",
        )

        # Invalid global config — loaded with strict=True during layer merge
        global_home = tmp_path / "home"
        global_home.mkdir(parents=True)
        global_vibe = global_home / ".vibe"
        global_vibe.mkdir(parents=True)
        (global_vibe / "settings.yaml").write_text(
            ": [invalid yaml\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(Path, "home", lambda: global_home)

        with pytest.raises(ConfigError, match="Invalid YAML"):
            load_config()

    def test_load_config_from_external_cwd(self, tmp_path: Path, monkeypatch) -> None:
        """Config loading works when CWD has no vibe3 config files."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
        # tmp_path is empty — no .vibe/, no config/v3/ — simulating external project
        config = load_config()
        # Should have agent_config from vibe3 installation defaults
        assert config.plan.agent_config.agent is not None
        assert config.run.agent_config.agent is not None
        assert config.review.agent_config.agent is not None


class TestLoadConfigTargetRepo:
    """Tests for load_config with target_repo parameter."""

    def test_load_config_with_target_repo(self, tmp_path: Path, monkeypatch) -> None:
        """Provide target_repo pointing to temp dir with .vibe/settings.yaml."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

        # Create target repo with project config
        target_repo = tmp_path / "target-repo"
        target_repo.mkdir()
        target_vibe = target_repo / ".vibe"
        target_vibe.mkdir()
        (target_vibe / "settings.yaml").write_text(
            "flow:\n  protected_branches:\n    - target-branch\n",
            encoding="utf-8",
        )

        # Load config with target_repo parameter
        config = load_config(target_repo=target_repo)
        assert config.flow.protected_branches == ["target-branch"]

    def test_load_config_invalid_project_yaml_error(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Invalid YAML in target repo's .vibe/settings.yaml raises ConfigError."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

        # Create target repo with invalid YAML
        target_repo = tmp_path / "target-repo"
        target_repo.mkdir()
        target_vibe = target_repo / ".vibe"
        target_vibe.mkdir()
        (target_vibe / "settings.yaml").write_text(
            ": [invalid yaml\n",
            encoding="utf-8",
        )

        with pytest.raises(ConfigError, match="Invalid YAML"):
            load_config(target_repo=target_repo)


class TestLoadRuntimeConfig:
    """Tests for load_runtime_config function."""

    def test_load_runtime_config_layering(self, tmp_path: Path, monkeypatch) -> None:
        """Set up four-layer temp structure, verify each layer's precedence."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

        # Repo base config (config/v3/settings.yaml)
        repo_config = tmp_path / "config" / "v3"
        repo_config.mkdir(parents=True)
        (repo_config / "settings.yaml").write_text(
            "run:\n  agent_config:\n    backend: repo-backend\n",
            encoding="utf-8",
        )

        # Global config (~/.vibe/settings.yaml)
        global_config = tmp_path / "home" / ".vibe"
        global_config.mkdir(parents=True)
        (global_config / "settings.yaml").write_text(
            "run:\n  agent_config:\n    backend: global-backend\n",
            encoding="utf-8",
        )

        # Project config (.vibe/settings.yaml)
        project_config = tmp_path / ".vibe"
        project_config.mkdir(parents=True)
        (project_config / "settings.yaml").write_text(
            "run:\n  agent_config:\n    backend: project-backend\n",
            encoding="utf-8",
        )

        config = load_runtime_config()
        # Project config is highest priority
        assert config.run.agent_config.backend == "project-backend"

    def test_load_runtime_config_cli_overrides(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Provide cli_overrides dict, verify highest priority."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

        # Create base config
        repo_config = tmp_path / "config" / "v3"
        repo_config.mkdir(parents=True)
        (repo_config / "settings.yaml").write_text(
            "run:\n  agent_config:\n    backend: base-backend\n",
            encoding="utf-8",
        )

        cli_overrides = {"run.agent_config.backend": "cli-backend"}
        config = load_runtime_config(cli_overrides=cli_overrides)
        assert config.run.agent_config.backend == "cli-backend"

    def test_load_runtime_config_agent_config_override(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Verify agent_config backend/model/agent can be overridden."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

        project_config = tmp_path / ".vibe"
        project_config.mkdir(parents=True)
        (project_config / "settings.yaml").write_text(
            "run:\n  agent_config:\n    backend: codex\n"
            "    model: gpt-4\n    agent: custom-agent\n",
            encoding="utf-8",
        )

        config = load_runtime_config()
        assert config.run.agent_config.backend == "codex"
        assert config.run.agent_config.model == "gpt-4"
        assert config.run.agent_config.agent == "custom-agent"

    def test_load_runtime_config_orchestra_override(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Verify orchestra fields can be overridden from project config."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
        # Clear env overrides that would interfere with config file values
        monkeypatch.delenv("VIBE_MODEL_MANAGER", raising=False)
        monkeypatch.delenv("VIBE_BACKEND_MANAGER", raising=False)

        # Mock apply_env_overrides to skip environment variable processing
        # This allows testing project config layering in isolation from user env vars
        from vibe3.config import env_override

        monkeypatch.setattr(
            env_override,
            "apply_env_overrides",
            lambda config_dict, rules=None: config_dict,
        )

        project_config = tmp_path / ".vibe"
        project_config.mkdir(parents=True)
        (project_config / "settings.yaml").write_text(
            "orchestra:\n  assignee_dispatch:\n"
            "    agent: orchestra-agent\n    backend: codex\n"
            "    model: gpt-4\n  scene_base_ref: custom-ref\n"
            "  repo: custom-repo\n",
            encoding="utf-8",
        )

        config = load_runtime_config()
        assert config.orchestra.assignee_dispatch.agent == "orchestra-agent"
        assert config.orchestra.assignee_dispatch.backend == "codex"
        assert config.orchestra.assignee_dispatch.model == "gpt-4"
        assert config.orchestra.scene_base_ref == "custom-ref"
        assert config.orchestra.repo == "custom-repo"


class TestLoadOrchestraConfigTargetRepo:
    """Tests for load_orchestra_config with target_repo parameter."""

    def test_load_orchestra_config_with_target_repo(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Verify load_orchestra_config respects target_repo parameter."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

        # Create target repo with orchestra config
        target_repo = tmp_path / "target-repo"
        target_repo.mkdir()
        target_vibe = target_repo / ".vibe"
        target_vibe.mkdir()
        (target_vibe / "settings.yaml").write_text(
            "orchestra:\n  scene_base_ref: target-ref\n  repo: target-repo\n",
            encoding="utf-8",
        )

        config = load_orchestra_config(target_repo=target_repo)
        assert config.scene_base_ref == "target-ref"
        assert config.repo == "target-repo"
