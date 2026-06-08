"""Tests for shared expand_config_variables utility."""

from __future__ import annotations

from pathlib import Path

from vibe3.config.utils import expand_config_variables


class TestExpandConfigVariables:
    """Tests for expand_config_variables shared function."""

    def test_expand_simple(self) -> None:
        """Simple variable reference resolves correctly."""
        config = {"paths": {"root": "/app"}, "file": "${paths.root}/data"}
        result = expand_config_variables(config)
        assert result["file"] == "/app/data"

    def test_expand_nested_path(self) -> None:
        """Nested path references resolve correctly."""
        config = {"a": {"b": "value"}, "c": "${a.b}_suffix"}
        result = expand_config_variables(config)
        assert result["c"] == "value_suffix"

    def test_expand_chained_references(self) -> None:
        """Chained references: A refs B, B refs C — full chain resolves."""
        config = {"base": "/tmp", "mid": "${base}/sub", "final": "${mid}/file.txt"}
        result = expand_config_variables(config)
        assert result["final"] == "/tmp/sub/file.txt"

    def test_expand_cycle_detection(self) -> None:
        """Circular references terminate without hanging; values stay unresolved."""
        config = {"a": "${b}", "b": "${a}"}
        result = expand_config_variables(config)
        assert result["a"] == "${b}"
        assert result["b"] == "${a}"

    def test_expand_missing_variable(self) -> None:
        """Unresolvable references keep original string."""
        config = {"val": "${nonexistent.key}"}
        result = expand_config_variables(config)
        assert result["val"] == "${nonexistent.key}"

    def test_expand_non_string_passthrough(self) -> None:
        """Int, bool, and list values passed through unchanged."""
        config = {"count": 42, "enabled": True, "items": [1, 2, 3]}
        result = expand_config_variables(config)
        assert result["count"] == 42
        assert result["enabled"] is True
        assert result["items"] == [1, 2, 3]

    def test_expand_dict_recursion(self) -> None:
        """Nested dict with var refs: inner and outer both expanded."""
        config = {
            "root": "/app",
            "nested": {"path": "${root}/inner", "ref": "${nested.path}/deep"},
        }
        result = expand_config_variables(config)
        assert result["nested"]["path"] == "/app/inner"
        assert result["nested"]["ref"] == "/app/inner/deep"

    def test_expand_tilde_home_directory(self) -> None:
        """~ prefix expanded via Path.expanduser()."""
        config = {"home_path": "~/.vibe"}
        result = expand_config_variables(config)
        assert result["home_path"] == str(Path("~/.vibe").expanduser())

    def test_expand_tilde_embedded_in_path(self) -> None:
        """Embedded /~/ in path also expanded."""
        config = {"embedded": "/tmp/~/data"}
        result = expand_config_variables(config)
        assert result["embedded"] == str(Path("/tmp/~/data").expanduser())

    def test_expand_deeply_nested_dict(self) -> None:
        """Variable references inside deeply nested dicts resolve correctly."""
        config = {
            "paths": {"root": "/app"},
            "level1": {
                "level2": {
                    "value": "${paths.root}/deep/file.txt",
                }
            },
        }
        result = expand_config_variables(config)
        assert result["level1"]["level2"]["value"] == "/app/deep/file.txt"

    def test_expand_dict_reference_keeps_original(self) -> None:
        """Reference to a dict value keeps original reference (not a dict)."""
        config = {"section": {"a": 1}, "ref": "${section}"}
        result = expand_config_variables(config)
        # Resolves to the dict itself, which gets str()-ed? No —
        # the code returns match.group(0) when current is a dict
        assert result["ref"] == "${section}"

    def test_expand_with_custom_context(self) -> None:
        """Explicit context param resolves against context, not config root."""
        config = {"val": "${external.key}"}
        context = {"external": {"key": "resolved"}}
        result = expand_config_variables(config, context=context)
        assert result["val"] == "resolved"

    def test_expand_context_defaults_to_config(self) -> None:
        """When context is None, config is used as resolution context."""
        config = {"base": "/root", "derived": "${base}/derived"}
        result = expand_config_variables(config)
        assert result["derived"] == "/root/derived"

    def test_expand_multiple_references_in_one_value(self) -> None:
        """Multiple ${...} references in a single string all resolve."""
        config = {
            "base": "/app",
            "sub": "data",
            "path": "${base}/${sub}/file.txt",
        }
        result = expand_config_variables(config)
        assert result["path"] == "/app/data/file.txt"
