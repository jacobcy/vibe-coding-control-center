"""Tests for AgentOptions dataclass."""

from dataclasses import FrozenInstanceError

import pytest

from vibe3.models.review_runner import AgentOptions


class TestAgentOptions:
    """Tests for AgentOptions dataclass - immutable configuration."""

    def test_default_options(self) -> None:
        """Default options should have None for agent/backend/model."""
        options = AgentOptions()
        assert options.agent is None
        assert options.model is None
        assert options.backend is None
        assert options.worktree is False
        assert options.timeout_seconds == 600

    def test_custom_options_with_agent(self) -> None:
        """Should support custom agent preset."""
        options = AgentOptions(
            agent="code-reviewer",
            timeout_seconds=300,
        )
        assert options.agent == "code-reviewer"
        assert options.model is None
        assert options.backend is None
        assert options.timeout_seconds == 300

    def test_custom_options_with_backend(self) -> None:
        """Should support backend + model specification."""
        options = AgentOptions(
            backend="claude",
            model="claude-3-opus",
            timeout_seconds=300,
        )
        assert options.agent is None
        assert options.backend == "claude"
        assert options.model == "claude-3-opus"
        assert options.timeout_seconds == 300

    def test_agent_and_backend_can_coexist(self) -> None:
        """Agent and backend can both be specified (for different purposes)."""
        options = AgentOptions(
            agent="code-reviewer",
            backend="claude",
            model="claude-sonnet-4-6",
        )
        assert options.agent == "code-reviewer"
        assert options.backend == "claude"
        assert options.model == "claude-sonnet-4-6"

    def test_options_are_frozen(self) -> None:
        """Options should be immutable (frozen dataclass)."""
        options = AgentOptions()
        with pytest.raises(FrozenInstanceError):
            options.agent = "other"  # type: ignore

    def test_model_can_be_overridden(self) -> None:
        """Model can be set to override default."""
        options = AgentOptions(model="claude-3-opus")
        assert options.model == "claude-3-opus"
