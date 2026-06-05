"""Tests for CLI overrides module."""

import dataclasses

import pytest

from vibe3.config.cli_overrides import (
    RoleCliOverrides,
    build_issue_role_cli_overrides,
    build_role_cli_overrides,
)


class TestRoleCliOverrides:
    """Tests for RoleCliOverrides dataclass."""

    def test_to_config_overrides_all_set(self) -> None:
        """Test config override dict with all fields set."""
        o = RoleCliOverrides(agent="a", backend="b", model="m", fresh_session=True)
        assert o.to_config_overrides("plan") == {
            "plan.agent_config.agent": "a",
            "plan.agent_config.backend": "b",
            "plan.agent_config.model": "m",
        }

    def test_to_config_overrides_defaults(self) -> None:
        """Test config override dict with defaults (empty)."""
        o = RoleCliOverrides()
        assert o.to_config_overrides("run") == {}

    def test_to_config_overrides_partial(self) -> None:
        """Test config override dict with partial fields."""
        o = RoleCliOverrides(backend="b")
        assert o.to_config_overrides("review") == {
            "review.agent_config.backend": "b",
        }

    def test_to_argv_all_set(self) -> None:
        """Test argv list with all fields set."""
        o = RoleCliOverrides(agent="a", backend="b", model="m", fresh_session=True)
        assert o.to_argv() == [
            "--agent",
            "a",
            "--backend",
            "b",
            "--model",
            "m",
            "--fresh-session",
        ]

    def test_to_argv_defaults(self) -> None:
        """Test argv list with defaults (empty)."""
        o = RoleCliOverrides()
        assert o.to_argv() == []

    def test_to_argv_partial(self) -> None:
        """Test argv list with partial fields."""
        o = RoleCliOverrides(agent="a", fresh_session=True)
        assert o.to_argv() == ["--agent", "a", "--fresh-session"]

    def test_frozen(self) -> None:
        """Test that dataclass is frozen (immutable)."""
        o = RoleCliOverrides(agent="a")
        with pytest.raises(dataclasses.FrozenInstanceError):
            o.agent = "b"

    def test_build_role_cli_overrides_delegates(self) -> None:
        """Test that build_role_cli_overrides delegates to RoleCliOverrides."""
        result = build_role_cli_overrides("plan", "a", "b", "m")
        assert result == RoleCliOverrides(
            agent="a", backend="b", model="m"
        ).to_config_overrides("plan")

    def test_build_issue_role_cli_overrides_delegates(self) -> None:
        """Test that build_issue_role_cli_overrides delegates to RoleCliOverrides."""
        result = build_issue_role_cli_overrides("reviewer", "a", "b", "m")
        assert result == RoleCliOverrides(
            agent="a", backend="b", model="m"
        ).to_config_overrides("review")

    def test_build_issue_role_cli_overrides_unknown_role(self) -> None:
        """Test that unknown role returns empty dict."""
        assert build_issue_role_cli_overrides("unknown", "a", "b", "m") == {}
