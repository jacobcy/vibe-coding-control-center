"""Tests for VibeConfig._expand_config_variables in vibe3.config.settings."""

from __future__ import annotations

from pathlib import Path

from vibe3.config.settings import VibeConfig


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
