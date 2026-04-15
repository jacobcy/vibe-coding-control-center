"""Tests for resolve_command_agent_options.

Tests the resolution priority logic for CLI overrides and config defaults.
"""

from unittest.mock import MagicMock

import pytest

from vibe3.config.settings import VibeConfig
from vibe3.execution.codeagent_support import resolve_command_agent_options


class TestResolveAgentOptions:
    """Tests for resolve_command_agent_options priority logic."""

    def test_cli_agent_overrides_config_agent(self) -> None:
        """CLI --agent should override config agent."""
        config = MagicMock(spec=VibeConfig)
        config.run = MagicMock()
        config.run.agent_config = MagicMock()
        config.run.agent_config.agent = "config-agent"
        config.run.agent_config.backend = "config-backend"
        config.run.agent_config.model = "config-model"
        config.run.agent_config.timeout_seconds = 3600

        result = resolve_command_agent_options(
            config=config, section="run", agent="cli-agent"
        )

        assert result.agent == "cli-agent"
        assert result.backend is None
        assert result.model is None
        assert result.timeout_seconds == 3600

    def test_cli_backend_overrides_config_backend(self) -> None:
        """CLI --backend should override config backend (no config model fallback)."""
        config = MagicMock(spec=VibeConfig)
        config.run = MagicMock()
        config.run.agent_config = MagicMock()
        config.run.agent_config.agent = None
        config.run.agent_config.backend = "config-backend"
        config.run.agent_config.model = "config-model"
        config.run.agent_config.timeout_seconds = 3600

        result = resolve_command_agent_options(
            config=config,
            section="run",
            backend="cli-backend",
            model="cli-model",
        )

        assert result.backend == "cli-backend"
        assert result.model == "cli-model"  # CLI model, not config model
        assert result.agent is None
        assert result.timeout_seconds == 3600

    def test_config_agent_takes_precedence_over_config_backend(self) -> None:
        """When config has both agent and backend, agent wins."""
        config = MagicMock(spec=VibeConfig)
        config.run = MagicMock()
        config.run.agent_config = MagicMock()
        config.run.agent_config.agent = "config-agent"
        config.run.agent_config.backend = "config-backend"
        config.run.agent_config.model = "config-model"
        config.run.agent_config.timeout_seconds = 3600

        result = resolve_command_agent_options(config=config, section="run")

        assert result.agent == "config-agent"
        assert result.backend is None
        assert result.model is None
        assert result.timeout_seconds == 3600

    def test_config_backend_used_when_no_agent(self) -> None:
        """Config backend/model should be used when agent is absent."""
        config = MagicMock(spec=VibeConfig)
        config.run = MagicMock()
        config.run.agent_config = MagicMock()
        config.run.agent_config.agent = None
        config.run.agent_config.backend = "config-backend"
        config.run.agent_config.model = "config-model"
        config.run.agent_config.timeout_seconds = 3600

        result = resolve_command_agent_options(config=config, section="run")

        assert result.backend == "config-backend"
        assert result.model == "config-model"
        assert result.agent is None
        assert result.timeout_seconds == 3600

    def test_cli_backend_ignores_config_model(self) -> None:
        """CLI --backend should not inherit config model (user must be explicit)."""
        config = MagicMock(spec=VibeConfig)
        config.run = MagicMock()
        config.run.agent_config = MagicMock()
        config.run.agent_config.agent = None
        config.run.agent_config.backend = "config-backend"
        config.run.agent_config.model = "config-model"
        config.run.agent_config.timeout_seconds = 3600

        result = resolve_command_agent_options(
            config=config, section="run", backend="cli-backend"
        )

        assert result.backend == "cli-backend"
        assert result.model is None  # No model from config
        assert result.agent is None
        assert result.timeout_seconds == 3600

    def test_no_config_raises_error(self) -> None:
        """Missing config should raise ValueError."""
        config = MagicMock(spec=VibeConfig)
        config.run = None

        with pytest.raises(ValueError, match="No agent configuration found"):
            resolve_command_agent_options(config=config, section="run")

    def test_empty_agent_config_raises_error(self) -> None:
        """Empty agent_config should raise ValueError."""
        config = MagicMock(spec=VibeConfig)
        config.run = MagicMock()
        config.run.agent_config = MagicMock()
        config.run.agent_config.agent = None
        config.run.agent_config.backend = None
        config.run.agent_config.model = None

        with pytest.raises(ValueError, match="No agent configuration found"):
            resolve_command_agent_options(config=config, section="run")

    def test_custom_timeout_preserved(self) -> None:
        """Custom timeout should be preserved through resolution."""
        config = MagicMock(spec=VibeConfig)
        config.run = MagicMock()
        config.run.agent_config = MagicMock()
        config.run.agent_config.agent = None
        config.run.agent_config.backend = "test-backend"
        config.run.agent_config.model = None
        config.run.agent_config.timeout_seconds = 3600

        result = resolve_command_agent_options(config=config, section="run")

        assert result.timeout_seconds == 3600

    def test_default_timeout_when_not_configured(self) -> None:
        """Default timeout (3600s) should be used when not configured."""
        config = MagicMock(spec=VibeConfig)
        config.run = MagicMock()
        config.run.agent_config = MagicMock()
        config.run.agent_config.agent = None
        config.run.agent_config.backend = "test-backend"
        config.run.agent_config.model = None
        # Use spec to prevent auto-creation of attributes
        del config.run.agent_config.timeout_seconds  # Remove the MagicMock

        result = resolve_command_agent_options(config=config, section="run")

        # Should use default timeout
        assert result.timeout_seconds == 3600

    def test_plan_section_uses_plan_config(self) -> None:
        """Plan section should use plan.agent_config."""
        config = MagicMock(spec=VibeConfig)
        config.plan = MagicMock()
        config.plan.agent_config = MagicMock()
        config.plan.agent_config.agent = "plan-agent"
        config.plan.agent_config.backend = None
        config.plan.agent_config.model = None
        config.plan.agent_config.timeout_seconds = 2400

        result = resolve_command_agent_options(config=config, section="plan")

        assert result.agent == "plan-agent"
        assert result.timeout_seconds == 2400

    def test_review_section_uses_review_config(self) -> None:
        """Review section should use review.agent_config."""
        config = MagicMock(spec=VibeConfig)
        config.review = MagicMock()
        config.review.agent_config = MagicMock()
        config.review.agent_config.agent = None
        config.review.agent_config.backend = "review-backend"
        config.review.agent_config.model = "review-model"
        config.review.agent_config.timeout_seconds = 1200

        result = resolve_command_agent_options(config=config, section="review")

        assert result.backend == "review-backend"
        assert result.model == "review-model"
        assert result.timeout_seconds == 1200

    def test_cli_agent_wins_over_cli_backend(self) -> None:
        """When both CLI --agent and --backend are passed, --agent wins."""
        config = MagicMock(spec=VibeConfig)
        config.run = MagicMock()
        config.run.agent_config = MagicMock()
        config.run.agent_config.timeout_seconds = 3600

        result = resolve_command_agent_options(
            config=config,
            section="run",
            agent="cli-agent",
            backend="cli-backend",
        )

        assert result.agent == "cli-agent"
        assert result.backend is None  # Backend ignored when agent is set
        assert result.model is None
