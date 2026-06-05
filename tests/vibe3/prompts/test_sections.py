"""Tests for prompt section builders."""

from pathlib import Path
from unittest.mock import MagicMock

from vibe3.config import ConventionResolver
from vibe3.prompts.sections import (
    build_tools_guide_section,
    resolve_common_rules_path,
)


class TestBuildToolsGuideSection:
    """Tests for build_tools_guide_section (unit test)."""

    def test_returns_none_if_not_configured(self) -> None:
        """Should return None if path is None."""
        result = build_tools_guide_section(None)
        assert result is None

    def test_returns_none_if_file_not_exists(self, tmp_path: Path) -> None:
        """Should return None if file does not exist."""
        result = build_tools_guide_section(str(tmp_path / "nonexistent.md"))
        assert result is None

    def test_reads_tools_guide(self, tmp_path: Path) -> None:
        """Should read tools guide from file."""
        tools_file = tmp_path / "tools.md"
        tools_file.write_text("Use `vibe3 inspect` for analysis.")

        result = build_tools_guide_section(str(tools_file))

        assert result is not None
        assert "## Available Tools" in result
        assert "vibe3 inspect" in result


class TestResolveCommonRulesPath:
    """Tests for resolve_common_rules_path helper."""

    def test_returns_configured_path_when_set(self) -> None:
        """Should return configured path if provided."""
        resolver = MagicMock(spec=ConventionResolver)

        result = resolve_common_rules_path("config/rules.md", resolver)

        assert result == "config/rules.md"
        # Should not call resolver if path is provided
        resolver.get_policy_path.assert_not_called()

    def test_falls_back_to_resolver_when_none(self) -> None:
        """Should fall back to resolver if agent_common_rules is None."""
        resolver = MagicMock(spec=ConventionResolver)
        resolver.get_policy_path.return_value = "default/rules.md"

        result = resolve_common_rules_path(None, resolver)

        assert result == "default/rules.md"
        resolver.get_policy_path.assert_called_once_with("common")

    def test_returns_none_when_both_sources_none(self) -> None:
        """Should return None if both configured path and resolver return None."""
        resolver = MagicMock(spec=ConventionResolver)
        resolver.get_policy_path.return_value = None

        result = resolve_common_rules_path(None, resolver)

        assert result is None
        resolver.get_policy_path.assert_called_once_with("common")
