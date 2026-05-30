"""Tests for VibeConfig._expand_config_variables and _load_supplementary."""

from __future__ import annotations

from pathlib import Path

import pytest

from vibe3.config import VibeConfig


class TestExpandConfigVariables:
    """Tests for VibeConfig._expand_config_variables classmethod."""

    def test_expand_config_variables_simple(self) -> None:
        config = {"paths": {"root": "/app"}, "file": "${paths.root}/data"}
        result = VibeConfig._expand_config_variables(config)
        assert result["file"] == "/app/data"

    def test_expand_config_variables_nested(self) -> None:
        """Chained references: A refs B, B refs C — full chain resolves."""
        config = {"base": "/tmp", "mid": "${base}/sub", "final": "${mid}/file.txt"}
        result = VibeConfig._expand_config_variables(config)
        assert result["final"] == "/tmp/sub/file.txt"

    def test_expand_config_variables_cycle(self) -> None:
        """Circular references terminate without hanging."""
        config = {"a": "${b}", "b": "${a}"}
        result = VibeConfig._expand_config_variables(config)
        # Should not hang; both keys should still be present
        assert "a" in result
        assert "b" in result

    def test_expand_config_variables_missing(self) -> None:
        """Unresolvable references keep original string."""
        config = {"val": "${nonexistent.key}"}
        result = VibeConfig._expand_config_variables(config)
        assert result["val"] == "${nonexistent.key}"

    def test_expand_config_variables_non_string(self) -> None:
        """Int, bool, and list values passed through unchanged."""
        config = {"count": 42, "enabled": True, "items": [1, 2, 3]}
        result = VibeConfig._expand_config_variables(config)
        assert result["count"] == 42
        assert result["enabled"] is True
        assert result["items"] == [1, 2, 3]

    def test_expand_config_variables_tilde(self) -> None:
        """~ prefix expanded via Path.expanduser()."""
        config = {"home_path": "~/.vibe"}
        result = VibeConfig._expand_config_variables(config)
        assert result["home_path"] == str(Path("~/.vibe").expanduser())

    def test_expand_config_variables_deeply_nested_dict(self) -> None:
        """Variable references inside deeply nested dicts resolve correctly."""
        config = {
            "paths": {"root": "/app"},
            "level1": {
                "level2": {
                    "value": "${paths.root}/deep/file.txt",
                }
            },
        }
        result = VibeConfig._expand_config_variables(config)
        assert result["level1"]["level2"]["value"] == "/app/deep/file.txt"

    def test_expand_config_variables_dict_ref_not_string(self) -> None:
        """Reference to a dict value keeps original reference (not a dict)."""
        config = {"section": {"a": 1}, "ref": "${section}"}
        result = VibeConfig._expand_config_variables(config)
        # Resolves to the dict itself, which gets str()-ed? No —
        # the code returns match.group(0) when current is a dict
        assert result["ref"] == "${section}"


class TestLoadSupplementaryPromptsRoot:
    """Tests for prompts_root path resolution in VibeConfig._load_supplementary."""

    def test_prompts_root_from_paths_config_takes_priority(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """paths.prompts_root in data overrides repo-local fallback paths."""
        prompts_dir = tmp_path / "assets" / "prompts"
        prompts_dir.mkdir(parents=True)
        prompts_file = prompts_dir / "prompts.yaml"
        # Use a valid _PROMPT_KEYS key: agent_prompt.global_notice
        prompts_file.write_text("agent_prompt:\n  global_notice: installed-notice\n")

        # Run from tmp_path so repo-local prompts paths do not exist
        monkeypatch.chdir(tmp_path)
        data: dict = {"paths": {"prompts_root": str(prompts_dir)}}

        result = VibeConfig._load_supplementary(data)

        assert result.get("agent_prompt", {}).get("global_notice") == "installed-notice"

    def test_prompts_root_absent_falls_back_to_repo_local(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When paths.prompts_root is absent, no prompts merge occurs."""
        monkeypatch.chdir(tmp_path)
        data: dict = {}

        result = VibeConfig._load_supplementary(data)

        # No prompts merged — agent_prompt should not appear
        assert "agent_prompt" not in result

    def test_prompts_root_set_but_prompts_yaml_missing_falls_back(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """paths.prompts_root present but prompts.yaml missing → no merge."""
        missing_dir = tmp_path / "missing"
        # Do not create the directory or file
        monkeypatch.chdir(tmp_path)

        data: dict = {"paths": {"prompts_root": str(missing_dir)}}

        result = VibeConfig._load_supplementary(data)

        assert "agent_prompt" not in result

    def test_empty_prompts_root_falls_back(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Empty string paths.prompts_root is treated as falsy and falls back."""
        # Run from tmp_path so repo-local prompts paths do not exist
        monkeypatch.chdir(tmp_path)
        data: dict = {"paths": {"prompts_root": ""}}

        result = VibeConfig._load_supplementary(data)

        # Empty string should be treated as falsy and not attempt path resolution
        assert "agent_prompt" not in result
