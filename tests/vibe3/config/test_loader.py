"""Tests for configuration loaders in vibe3.config.loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from vibe3.config.loader import (
    _deep_merge,
    _expand_variables,
    load_config,
    load_yaml_config,
)
from vibe3.config.settings import VibeConfig
from vibe3.exceptions import ConfigError


class TestExpandVariables:
    """Tests for _expand_variables pure function."""

    def test_expand_variables_simple(self) -> None:
        config = {"paths": {"root": "/app"}, "file": "${paths.root}/data"}
        result = _expand_variables(config)
        assert result["file"] == "/app/data"

    def test_expand_variables_nested(self) -> None:
        config = {"a": {"b": "value"}, "c": "${a.b}_suffix"}
        result = _expand_variables(config)
        assert result["c"] == "value_suffix"

    def test_expand_variables_chained(self) -> None:
        """A refs B, B refs C — full chain resolves."""
        config = {"base": "/tmp", "mid": "${base}/sub", "final": "${mid}/file.txt"}
        result = _expand_variables(config)
        assert result["final"] == "/tmp/sub/file.txt"

    def test_expand_variables_cycle(self) -> None:
        """Circular references terminate without hanging; both keys present."""
        config = {"a": "${b}", "b": "${a}"}
        result = _expand_variables(config)
        assert "a" in result
        assert "b" in result
        # Both should be unresolved since they reference each other

    def test_expand_variables_missing(self) -> None:
        """Unresolvable references keep original string."""
        config = {"val": "${paths.missing}"}
        result = _expand_variables(config)
        assert result["val"] == "${paths.missing}"

    def test_expand_variables_non_string(self) -> None:
        """Int and list values passed through unchanged."""
        config = {"count": 42, "items": [1, 2, 3]}
        result = _expand_variables(config)
        assert result["count"] == 42
        assert result["items"] == [1, 2, 3]

    def test_expand_variables_dict_recursion(self) -> None:
        """Nested dict with var refs: inner and outer both expanded."""
        config = {
            "root": "/app",
            "nested": {"path": "${root}/inner", "ref": "${nested.path}/deep"},
        }
        result = _expand_variables(config)
        assert result["nested"]["path"] == "/app/inner"
        assert result["nested"]["ref"] == "/app/inner/deep"

    def test_expand_variables_tilde_expansion(self) -> None:
        """~ prefix expanded via Path.expanduser(), but /~/ embedded is not."""
        config = {"home_path": "~/data", "embedded": "/tmp/~/data"}
        result = _expand_variables(config)
        assert result["home_path"] == str(Path("~/data").expanduser())
        assert result["embedded"] == str(Path("/tmp/~/data").expanduser())

    def test_expand_variables_with_context(self) -> None:
        """Explicit context param resolves against context, not config root."""
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
