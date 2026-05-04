"""Tests for ExecutionRolePolicyService."""

from unittest.mock import patch

import pytest

from vibe3.execution.execution_role_policy import (
    ConcurrencyClass,
    ExecutionRolePolicyService,
    PromptContract,
    SessionStrategy,
)
from vibe3.models.orchestra_config import (
    AssigneeDispatchConfig,
    GovernanceConfig,
    OrchestraConfig,
    SupervisorHandoffConfig,
)
from vibe3.models.review_runner import AgentOptions


@pytest.fixture
def sample_config() -> OrchestraConfig:
    """Create a sample orchestra config for testing."""
    return OrchestraConfig(
        max_concurrent_flows=3,
        assignee_dispatch=AssigneeDispatchConfig(
            enabled=True,
            use_worktree=True,
            backend="claude",
            prompt_template="orchestra.assignee_dispatch.manager",
            timeout_seconds=3600,
        ),
        governance=GovernanceConfig(
            enabled=True,
            backend="openai",
            prompt_template="orchestra.governance.plan",
            supervisor_file="supervisor/governance/assignee-pool.md",
        ),
        supervisor_handoff=SupervisorHandoffConfig(
            enabled=True,
            backend="claude",
            prompt_template="orchestra.supervisor.apply",
            supervisor_file="supervisor/apply.md",
        ),
    )


def test_resolve_backend_manager(sample_config: OrchestraConfig) -> None:
    """Test backend resolution for manager role."""
    service = ExecutionRolePolicyService(config=sample_config)
    backend = service.resolve_backend("manager")
    assert backend == "claude"


def test_resolve_backend_governance(sample_config: OrchestraConfig) -> None:
    """Test backend resolution for governance role."""
    service = ExecutionRolePolicyService(config=sample_config)
    backend = service.resolve_backend("governance")
    assert backend == "openai"


def test_resolve_backend_unknown_role(sample_config: OrchestraConfig) -> None:
    """Test backend resolution for unknown role raises error."""
    service = ExecutionRolePolicyService(config=sample_config)
    with pytest.raises(ValueError, match="Unknown role"):
        service.resolve_backend("unknown_role")


def test_resolve_prompt_contract_manager(sample_config: OrchestraConfig) -> None:
    """Test prompt contract resolution for manager role."""
    service = ExecutionRolePolicyService(config=sample_config)
    contract = service.resolve_prompt_contract("manager")

    assert isinstance(contract, PromptContract)
    assert contract.template == "orchestra.assignee_dispatch.manager"


def test_resolve_prompt_contract_supervisor(sample_config: OrchestraConfig) -> None:
    """Test prompt contract resolution for supervisor role."""
    service = ExecutionRolePolicyService(config=sample_config)
    contract = service.resolve_prompt_contract("supervisor")

    assert isinstance(contract, PromptContract)
    assert contract.template == "orchestra.supervisor.apply"


def test_resolve_session_strategy_manager(sample_config: OrchestraConfig) -> None:
    """Test session strategy resolution for manager role."""
    service = ExecutionRolePolicyService(config=sample_config)
    strategy = service.resolve_session_strategy("manager")

    assert isinstance(strategy, SessionStrategy)
    # Manager with use_worktree=True and async_mode=True should use tmux
    assert strategy.mode == "tmux"
    assert strategy.timeout == 3600


def test_resolve_session_strategy_unknown_role(sample_config: OrchestraConfig) -> None:
    """Test session strategy for unknown role defaults to async."""
    service = ExecutionRolePolicyService(config=sample_config)
    strategy = service.resolve_session_strategy("unknown_role")

    assert isinstance(strategy, SessionStrategy)
    assert strategy.mode == "async"


def test_resolve_concurrency_class_manager(sample_config: OrchestraConfig) -> None:
    """Test concurrency class resolution for manager role."""
    service = ExecutionRolePolicyService(config=sample_config)
    concurrency = service.resolve_concurrency_class("manager")

    assert isinstance(concurrency, ConcurrencyClass)
    assert concurrency.max_concurrent == 3  # From max_concurrent_flows
    assert concurrency.semaphore_key == "manager"


def test_resolve_concurrency_class_other_role(sample_config: OrchestraConfig) -> None:
    """Test concurrency class resolution for non-manager role."""
    service = ExecutionRolePolicyService(config=sample_config)
    concurrency = service.resolve_concurrency_class("planner")

    assert isinstance(concurrency, ConcurrencyClass)
    assert concurrency.max_concurrent == 10  # Default for agents
    assert concurrency.semaphore_key == "planner"


def test_all_roles_resolve_backend(sample_config: OrchestraConfig) -> None:
    """Test that all valid orchestra roles can resolve backend."""
    service = ExecutionRolePolicyService(config=sample_config)

    # Only orchestra roles are handled by ExecutionRolePolicyService
    # Command roles (planner/executor/reviewer) are handled by agent_resolver.py
    roles = ["manager", "supervisor", "governance"]
    for role in roles:
        backend = service.resolve_backend(role)
        assert isinstance(backend, str)
        assert isinstance(backend, str)
        assert backend in ["claude", "openai"]


def test_all_roles_resolve_prompt_contract(sample_config: OrchestraConfig) -> None:
    """Test that all valid orchestra roles can resolve prompt contract."""
    service = ExecutionRolePolicyService(config=sample_config)

    # Only orchestra roles are handled by ExecutionRolePolicyService
    roles = ["manager", "supervisor", "governance"]
    for role in roles:
        contract = service.resolve_prompt_contract(role)
        assert isinstance(contract, PromptContract)
        assert contract.template  # Non-empty template


@patch("vibe3.execution.execution_role_policy.sync_models_json")
@patch(
    "vibe3.execution.execution_role_policy.resolve_backend_effective_agent_options",
    side_effect=lambda options: options,
)
def test_resolve_effective_agent_options_syncs_models(
    mock_resolve_effective, mock_sync, sample_config: OrchestraConfig
) -> None:
    """Effective resolution should reuse raw policy and sync models once."""
    service = ExecutionRolePolicyService(config=sample_config)

    result = service.resolve_effective_agent_options("manager")

    assert isinstance(result, AgentOptions)
    mock_resolve_effective.assert_called_once()
    mock_sync.assert_called_once_with(result)
