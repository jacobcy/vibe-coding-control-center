"""Regression tests for agent_resolver public API."""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.execution.agent_resolver import (
    resolve_governance_agent_options,
    resolve_manager_agent_options,
    resolve_supervisor_agent_options,
)
from vibe3.execution.execution_role_policy import ExecutionRolePolicyService
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.review_runner import AgentOptions


@patch.object(
    ExecutionRolePolicyService,
    "resolve_effective_agent_options",
    return_value=AgentOptions(backend="claude", model="sonnet"),
)
def test_resolve_governance_returns_agent_options(mock_resolve):
    config = OrchestraConfig()
    result = resolve_governance_agent_options(config)
    assert isinstance(result, AgentOptions)
    mock_resolve.assert_called_once_with("governance")


@patch.object(
    ExecutionRolePolicyService,
    "resolve_effective_agent_options",
    return_value=AgentOptions(backend="claude", model="sonnet"),
)
def test_resolve_supervisor_returns_agent_options(mock_resolve):
    config = OrchestraConfig()
    result = resolve_supervisor_agent_options(config)
    assert isinstance(result, AgentOptions)
    mock_resolve.assert_called_once_with("supervisor")


@patch.object(
    ExecutionRolePolicyService,
    "resolve_effective_agent_options",
    return_value=AgentOptions(backend="gemini", model="gemini-3-flash-preview"),
)
def test_resolve_manager_returns_agent_options(mock_resolve):
    config = OrchestraConfig()
    config.assignee_dispatch.backend = "gemini"
    config.assignee_dispatch.model = "gemini-3-flash-preview"
    runtime_config = MagicMock()
    result = resolve_manager_agent_options(config, runtime_config)
    assert isinstance(result, AgentOptions)
    mock_resolve.assert_called_once_with("manager")


def test_resolve_manager_requires_assignee_dispatch_config():
    config = OrchestraConfig()
    runtime_config = MagicMock()

    with patch.object(
        ExecutionRolePolicyService,
        "resolve_effective_agent_options",
    ) as mock_resolve:
        with pytest.raises(ValueError, match="assignee_dispatch"):
            resolve_manager_agent_options(config, runtime_config)
    mock_resolve.assert_not_called()
