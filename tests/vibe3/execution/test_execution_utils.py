"""Consolidated tests for execution utility modules."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.clients.store_context import get_store
from vibe3.execution.execution_role_policy import (
    ConcurrencyClass,
    ExecutionRolePolicyService,
    PromptContract,
    SessionStrategy,
)
from vibe3.execution.issue_role_support import (
    build_issue_async_cli_request,
    build_issue_sync_prompt_request,
    resolve_async_cli_project_root,
    resolve_orchestra_repo_root,
)
from vibe3.execution.role_contracts import WorktreeRequirement
from vibe3.execution.session_service import load_session_id
from vibe3.models.orchestra_config import (
    AssigneeDispatchConfig,
    GovernanceConfig,
    OrchestraConfig,
    SupervisorHandoffConfig,
)
from vibe3.models.orchestration import IssueInfo
from vibe3.models.review_runner import AgentOptions

MAIN_REPO = Path("/test/repos/vibe-center/main")
WORKTREE_REPO = Path("/test/repos/vibe-center/main/.worktrees/wt-dev")


class TestSessionService:
    """Tests for shared agent execution service."""

    @patch("vibe3.execution.session_service.SessionRegistryService")
    @patch("vibe3.execution.session_service.GitClient")
    def test_load_session_id_returns_registry_session(
        self, git_cls: MagicMock, registry_cls: MagicMock
    ) -> None:
        """load_session_id should return session from registry."""
        git_cls.return_value.get_current_branch.return_value = "task/demo"
        registry = MagicMock()
        registry.get_truly_live_sessions_for_branch.return_value = [
            {"role": "executor", "backend_session_id": "sess-123"}
        ]
        registry_cls.return_value = registry

        session_id = load_session_id("executor")

        assert session_id == "sess-123"

    @patch("vibe3.execution.session_service.SessionRegistryService")
    def test_load_session_id_supports_manager_role_with_explicit_branch(
        self, registry_cls: MagicMock
    ) -> None:
        """load_session_id should return manager session from registry."""
        registry = MagicMock()
        registry.get_truly_live_sessions_for_branch.return_value = [
            {"role": "manager", "backend_session_id": "sess-manager"}
        ]
        registry_cls.return_value = registry

        session_id = load_session_id("manager", branch="dev/issue-430")

        assert session_id == "sess-manager"

    @patch("vibe3.execution.session_service.SessionRegistryService")
    @patch("vibe3.execution.session_service.GitClient")
    def test_load_session_id_returns_none_when_no_matching_role(
        self, git_cls: MagicMock, registry_cls: MagicMock
    ) -> None:
        """load_session_id should return None when no session matches role."""
        git_cls.return_value.get_current_branch.return_value = "task/demo"
        registry = MagicMock()
        registry.get_truly_live_sessions_for_branch.return_value = [
            {"role": "planner", "backend_session_id": "sess-123"}
        ]
        registry_cls.return_value = registry

        session_id = load_session_id("executor")

        assert session_id is None

    @patch("vibe3.execution.session_service.SessionRegistryService")
    @patch("vibe3.execution.session_service.GitClient")
    def test_load_session_id_ignores_tmux_session_names(
        self, git_cls: MagicMock, registry_cls: MagicMock
    ) -> None:
        """load_session_id should ignore session IDs that look like tmux names."""
        git_cls.return_value.get_current_branch.return_value = "task/demo"
        registry = MagicMock()
        registry.get_truly_live_sessions_for_branch.return_value = [
            {"role": "executor", "backend_session_id": "vibe3-run-issue-451"}
        ]
        registry_cls.return_value = registry

        session_id = load_session_id("executor")

        # vibe3-* session IDs are tmux names, not valid wrapper sessions
        assert session_id is None


class TestStoreContext:
    """Tests for SQLiteClient context manager."""

    def test_get_store_provides_client(self) -> None:
        """get_store should yield SQLiteClient instance."""
        from vibe3.clients.sqlite_client import SQLiteClient

        with get_store() as store:
            assert isinstance(store, SQLiteClient)

    def test_get_store_context_isolation(self) -> None:
        """get_store should create new instance each time."""
        instances = []

        with get_store() as store1:
            instances.append(id(store1))

        with get_store() as store2:
            instances.append(id(store2))

        # Each call should create new instance
        assert instances[0] != instances[1]


class TestIssueRoleSupport:
    """Tests for issue role support helpers."""

    def test_resolve_orchestra_repo_root_prefers_git_common_dir_parent(
        self,
    ) -> None:
        """Normal orchestra operations should anchor to the main repository root."""
        with patch("vibe3.execution.issue_role_support.GitClient") as mock_git:
            mock_git.return_value.get_git_common_dir.return_value = f"{MAIN_REPO}/.git"

            root = resolve_orchestra_repo_root()

        assert root == MAIN_REPO

    def test_resolve_async_cli_project_root_defaults_to_repo_root(self) -> None:
        """Without debug override, async child should run main-repo code."""
        root = resolve_async_cli_project_root(MAIN_REPO)
        assert root == MAIN_REPO

    def test_resolve_async_cli_project_root_uses_debug_override(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Debug mode should run async child from the current worktree code root."""
        monkeypatch.setenv("VIBE3_REPO_MODELS_ROOT", str(WORKTREE_REPO))

        root = resolve_async_cli_project_root(MAIN_REPO)

        assert root == WORKTREE_REPO

    def test_build_issue_async_cli_request_uses_main_repo_by_default(
        self,
    ) -> None:
        """Async issue self-invocation should target main repo code in normal mode."""
        issue = IssueInfo(number=431, title="Test issue", labels=[])

        request = build_issue_async_cli_request(
            role="manager",
            issue=issue,
            target_branch="task/issue-431",
            command_args=["internal", "manager", "431", "--no-async"],
            actor="agent:manager",
            execution_name="vibe3-manager-issue-431",
            refs={},
            worktree_requirement=WorktreeRequirement.PERMANENT,
            repo_path=MAIN_REPO,
        )

        assert request.cmd is not None
        assert request.cmd[3] == str(MAIN_REPO)
        assert request.cmd[6] == str(MAIN_REPO / "src/vibe3/cli.py")
        assert request.repo_path == str(MAIN_REPO)

    def test_build_issue_async_cli_request_uses_debug_code_root_override(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Debug serve mode should only override code root, not orchestration repo."""
        monkeypatch.setenv("VIBE3_REPO_MODELS_ROOT", str(WORKTREE_REPO))
        issue = IssueInfo(number=431, title="Test issue", labels=[])

        request = build_issue_async_cli_request(
            role="manager",
            issue=issue,
            target_branch="task/issue-431",
            command_args=["internal", "manager", "431", "--no-async"],
            actor="agent:manager",
            execution_name="vibe3-manager-issue-431",
            refs={},
            worktree_requirement=WorktreeRequirement.PERMANENT,
            repo_path=MAIN_REPO,
        )

        assert request.cmd is not None
        assert request.cmd[3] == str(WORKTREE_REPO)
        assert request.cmd[6] == str(WORKTREE_REPO / "src/vibe3/cli.py")
        # Worktree creation / shared state still anchor to main repo root.
        assert request.repo_path == str(MAIN_REPO)

    def test_build_issue_sync_prompt_request_with_session_does_not_pin_cwd(
        self,
    ) -> None:
        """Retry sync requests should still let coordinator resolve the worktree cwd."""
        issue = IssueInfo(number=431, title="Test issue", labels=[])

        request = build_issue_sync_prompt_request(
            role="manager",
            issue=issue,
            target_branch="task/issue-431",
            prompt="test prompt",
            task="test task",
            options=object(),
            actor="agent:manager",
            execution_name="vibe3-manager-issue-431",
            worktree_requirement=WorktreeRequirement.PERMANENT,
            session_id="session-431",
            repo_path=MAIN_REPO,
        )

        assert request.refs["session_id"] == "session-431"
        assert request.cwd is None


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
        ),
        supervisor_handoff=SupervisorHandoffConfig(
            enabled=True,
            backend="claude",
            prompt_template="orchestra.supervisor.apply",
        ),
    )


class TestExecutionRolePolicy:
    """Tests for ExecutionRolePolicyService."""

    def test_resolve_backend_manager(self, sample_config: OrchestraConfig) -> None:
        """Test backend resolution for manager role."""
        service = ExecutionRolePolicyService(config=sample_config)
        backend = service.resolve_backend("manager")
        assert backend == "claude"

    def test_resolve_backend_governance(self, sample_config: OrchestraConfig) -> None:
        """Test backend resolution for governance role."""
        service = ExecutionRolePolicyService(config=sample_config)
        backend = service.resolve_backend("governance")
        assert backend == "openai"

    def test_resolve_backend_unknown_role(self, sample_config: OrchestraConfig) -> None:
        """Test backend resolution for unknown role raises error."""
        service = ExecutionRolePolicyService(config=sample_config)
        with pytest.raises(ValueError, match="Unknown role"):
            service.resolve_backend("unknown_role")

    def test_resolve_prompt_contract_manager(
        self, sample_config: OrchestraConfig
    ) -> None:
        """Test prompt contract resolution for manager role."""
        service = ExecutionRolePolicyService(config=sample_config)
        contract = service.resolve_prompt_contract("manager")

        assert isinstance(contract, PromptContract)
        assert contract.template == "orchestra.assignee_dispatch.manager"

    def test_resolve_prompt_contract_supervisor(
        self, sample_config: OrchestraConfig
    ) -> None:
        """Test prompt contract resolution for supervisor role."""
        service = ExecutionRolePolicyService(config=sample_config)
        contract = service.resolve_prompt_contract("supervisor")

        assert isinstance(contract, PromptContract)
        assert contract.template == "orchestra.supervisor.apply"

    def test_resolve_session_strategy_manager(
        self, sample_config: OrchestraConfig
    ) -> None:
        """Test session strategy resolution for manager role."""
        service = ExecutionRolePolicyService(config=sample_config)
        strategy = service.resolve_session_strategy("manager")

        assert isinstance(strategy, SessionStrategy)
        # Manager with use_worktree=True and async_mode=True should use tmux
        assert strategy.mode == "tmux"
        assert strategy.timeout == 3600

    def test_resolve_session_strategy_unknown_role(
        self, sample_config: OrchestraConfig
    ) -> None:
        """Test session strategy for unknown role defaults to async."""
        service = ExecutionRolePolicyService(config=sample_config)
        strategy = service.resolve_session_strategy("unknown_role")

        assert isinstance(strategy, SessionStrategy)
        assert strategy.mode == "async"

    def test_resolve_concurrency_class_manager(
        self, sample_config: OrchestraConfig
    ) -> None:
        """Test concurrency class resolution for manager role."""
        service = ExecutionRolePolicyService(config=sample_config)
        concurrency = service.resolve_concurrency_class("manager")

        assert isinstance(concurrency, ConcurrencyClass)
        assert concurrency.max_concurrent == 3  # From max_concurrent_flows
        assert concurrency.semaphore_key == "manager"

    def test_resolve_concurrency_class_other_role(
        self, sample_config: OrchestraConfig
    ) -> None:
        """Test concurrency class resolution for non-manager role."""
        service = ExecutionRolePolicyService(config=sample_config)
        concurrency = service.resolve_concurrency_class("planner")

        assert isinstance(concurrency, ConcurrencyClass)
        assert concurrency.max_concurrent == 10  # Default for agents
        assert concurrency.semaphore_key == "planner"

    def test_all_roles_resolve_backend(self, sample_config: OrchestraConfig) -> None:
        """Test that all valid orchestra roles can resolve backend."""
        service = ExecutionRolePolicyService(config=sample_config)

        # Only orchestra roles are handled by ExecutionRolePolicyService
        roles = ["manager", "supervisor", "governance"]
        for role in roles:
            backend = service.resolve_backend(role)
            assert isinstance(backend, str)
            assert isinstance(backend, str)
            assert backend in ["claude", "openai"]

    def test_all_roles_resolve_prompt_contract(
        self, sample_config: OrchestraConfig
    ) -> None:
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
        self,
        mock_resolve_effective: MagicMock,
        mock_sync: MagicMock,
        sample_config: OrchestraConfig,
    ) -> None:
        """Effective resolution should reuse raw policy and sync models once."""
        service = ExecutionRolePolicyService(config=sample_config)

        result = service.resolve_effective_agent_options("manager")

        assert isinstance(result, AgentOptions)
        mock_resolve_effective.assert_called_once()
        mock_sync.assert_called_once_with(result)
