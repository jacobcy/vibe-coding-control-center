"""Regression tests for agent_resolver public API."""

from unittest.mock import MagicMock, patch

from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.review_runner import AgentOptions
from vibe3.runtime.agent_resolver import (
    resolve_governance_agent_options,
    resolve_manager_agent_options,
    resolve_supervisor_agent_options,
)


def _mock_resolve(options: AgentOptions) -> AgentOptions:
    """Return options unchanged (simulates resolve_effective_agent_options)."""
    return options


@patch("vibe3.runtime.agent_resolver.sync_models_json")
@patch(
    "vibe3.runtime.agent_resolver.resolve_effective_agent_options",
    side_effect=_mock_resolve,
)
def test_resolve_governance_returns_agent_options(mock_resolve, mock_sync):
    config = OrchestraConfig()
    result = resolve_governance_agent_options(config)
    assert isinstance(result, AgentOptions)
    mock_resolve.assert_called_once()
    mock_sync.assert_called_once()


@patch("vibe3.runtime.agent_resolver.sync_models_json")
@patch(
    "vibe3.runtime.agent_resolver.resolve_effective_agent_options",
    side_effect=_mock_resolve,
)
def test_resolve_supervisor_returns_agent_options(mock_resolve, mock_sync):
    config = OrchestraConfig()
    result = resolve_supervisor_agent_options(config)
    assert isinstance(result, AgentOptions)
    mock_resolve.assert_called_once()
    mock_sync.assert_called_once()


@patch("vibe3.runtime.agent_resolver.sync_models_json")
@patch(
    "vibe3.runtime.agent_resolver.resolve_effective_agent_options",
    side_effect=_mock_resolve,
)
def test_resolve_manager_returns_agent_options(mock_resolve, mock_sync):
    config = OrchestraConfig()
    config.assignee_dispatch.backend = "gemini"
    config.assignee_dispatch.model = "gemini-3-flash-preview"
    runtime_config = MagicMock()
    result = resolve_manager_agent_options(config, runtime_config)
    assert isinstance(result, AgentOptions)
    mock_resolve.assert_called_once()
    mock_sync.assert_called_once()


def test_resolve_manager_requires_assignee_dispatch_config():
    config = OrchestraConfig()
    runtime_config = MagicMock()

    with patch("vibe3.runtime.agent_resolver.sync_models_json") as mock_sync:
        try:
            resolve_manager_agent_options(config, runtime_config)
        except ValueError as exc:
            assert "assignee_dispatch" in str(exc)
        else:
            raise AssertionError("Expected ValueError when manager config is missing")

    mock_sync.assert_not_called()
