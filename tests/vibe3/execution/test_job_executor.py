"""Tests for JobExecutor service."""

from unittest.mock import Mock, patch

import pytest

from vibe3.clients import SQLiteClient
from vibe3.execution.command_adapter import CommandAdapterRegistry
from vibe3.execution.execution_lifecycle import ExecutionLifecycleService
from vibe3.execution.job_executor import (
    COMMAND_TYPE_TO_EXECUTION_ROLE,
    JobExecutor,
)
from vibe3.models import CommandType, ExecutionLaunchResult, JobContext, JobEnvelope


@pytest.fixture
def mock_store() -> SQLiteClient:
    """Mock SQLite client."""
    return Mock(spec=SQLiteClient)


@pytest.fixture
def mock_lifecycle() -> ExecutionLifecycleService:
    """Mock execution lifecycle service."""
    mock = Mock(spec=ExecutionLifecycleService)
    return mock


@pytest.fixture
def test_envelope() -> JobEnvelope:
    """Test job envelope for PLAN command."""
    return JobEnvelope(
        command_type=CommandType.PLAN,
        issue_number=123,
        branch="task/issue-123-test",
        source="cli-manual",
        actor="test:executor",
    )


class TestCommandTypeToExecutionRoleMapping:
    """Tests for CommandType to ExecutionRole mapping correctness."""

    def test_all_command_types_mapped(self) -> None:
        """All 6 CommandType values should have ExecutionRole mapping."""
        expected_types = {
            CommandType.PLAN,
            CommandType.RUN,
            CommandType.REVIEW,
            CommandType.MANAGER,
            CommandType.GOVERNANCE_SCAN,
            CommandType.SUPERVISOR_APPLY,
        }
        assert set(COMMAND_TYPE_TO_EXECUTION_ROLE.keys()) == expected_types

    def test_plan_maps_to_planner(self) -> None:
        """PLAN command type should map to 'planner' role."""
        assert COMMAND_TYPE_TO_EXECUTION_ROLE[CommandType.PLAN] == "planner"

    def test_run_maps_to_executor(self) -> None:
        """RUN command type should map to 'executor' role."""
        assert COMMAND_TYPE_TO_EXECUTION_ROLE[CommandType.RUN] == "executor"

    def test_review_maps_to_reviewer(self) -> None:
        """REVIEW command type should map to 'reviewer' role."""
        assert COMMAND_TYPE_TO_EXECUTION_ROLE[CommandType.REVIEW] == "reviewer"

    def test_manager_maps_to_manager(self) -> None:
        """MANAGER command type should map to 'manager' role."""
        assert COMMAND_TYPE_TO_EXECUTION_ROLE[CommandType.MANAGER] == "manager"

    def test_governance_maps_to_governance(self) -> None:
        """GOVERNANCE_SCAN command type should map to 'governance' role."""
        assert (
            COMMAND_TYPE_TO_EXECUTION_ROLE[CommandType.GOVERNANCE_SCAN] == "governance"
        )

    def test_supervisor_maps_to_supervisor(self) -> None:
        """SUPERVISOR_APPLY command type should map to 'supervisor' role."""
        assert (
            COMMAND_TYPE_TO_EXECUTION_ROLE[CommandType.SUPERVISOR_APPLY] == "supervisor"
        )


class TestJobExecutorInit:
    """Tests for JobExecutor initialization."""

    def test_init_with_registry_and_store(self, mock_store: SQLiteClient) -> None:
        """Executor should initialize with registry and store."""
        registry = CommandAdapterRegistry()
        executor = JobExecutor(registry, mock_store)
        assert executor._registry is registry
        assert executor._lifecycle is not None


class TestBuildContext:
    """Tests for _build_context method."""

    @patch("vibe3.execution.job_executor.resolve_orchestra_repo_root")
    def test_build_context_populates_issue_and_branch(
        self,
        mock_resolve_repo: Mock,
        mock_store: SQLiteClient,
        test_envelope: JobEnvelope,
    ) -> None:
        """Context should include issue_number and branch from envelope."""
        mock_resolve_repo.return_value = Mock(
            worktree="/path/to/worktree", repo="/path/to/repo"
        )

        registry = CommandAdapterRegistry()
        executor = JobExecutor(registry, mock_store)

        with patch.object(executor, "_lifecycle", Mock()):
            context = executor._build_context(test_envelope)

        assert context.issue_number == 123
        assert context.branch == "task/issue-123-test"


class TestExecute:
    """Tests for execute method."""

    def test_execute_resolves_adapter(
        self, mock_store: SQLiteClient, test_envelope: JobEnvelope
    ) -> None:
        """Executor should resolve adapter from registry."""
        registry = Mock(spec=CommandAdapterRegistry)
        mock_adapter = Mock()
        mock_adapter.entry.import_path = "vibe3.roles.plan"
        mock_adapter.callable = Mock(role_name="planner")
        registry.resolve.return_value = mock_adapter

        executor = JobExecutor(registry, mock_store)
        mock_lifecycle = Mock(spec=ExecutionLifecycleService)
        executor._lifecycle = mock_lifecycle

        # Mock the execution path to return success
        with patch.object(executor, "_execute_issue_role") as mock_execute_role:
            mock_execute_role.return_value = ExecutionLaunchResult(
                launched=True, session_id="session-123"
            )

            result = executor.execute(test_envelope)

        # Verify adapter was resolved
        registry.resolve.assert_called_once_with(CommandType.PLAN)
        assert result.adapter_path == "vibe3.roles.plan"

    def test_execute_records_lifecycle_started(
        self, mock_store: SQLiteClient, test_envelope: JobEnvelope
    ) -> None:
        """Executor should record started lifecycle event."""
        registry = Mock(spec=CommandAdapterRegistry)
        mock_adapter = Mock()
        mock_adapter.entry.import_path = "vibe3.roles.plan"
        mock_adapter.callable = Mock(role_name="planner")
        registry.resolve.return_value = mock_adapter

        executor = JobExecutor(registry, mock_store)
        mock_lifecycle = Mock(spec=ExecutionLifecycleService)
        executor._lifecycle = mock_lifecycle

        with patch.object(executor, "_execute_issue_role") as mock_execute_role:
            mock_execute_role.return_value = ExecutionLaunchResult(launched=True)

            executor.execute(test_envelope)

        # Verify lifecycle started was called
        mock_lifecycle.record_started.assert_called_once()
        call_args = mock_lifecycle.record_started.call_args
        assert call_args.kwargs["role"] == "planner"
        assert call_args.kwargs["target"] == "task/issue-123-test"
        assert call_args.kwargs["actor"] == "test:executor"

    def test_execute_returns_launched_result(
        self, mock_store: SQLiteClient, test_envelope: JobEnvelope
    ) -> None:
        """Executor should return launched JobResult for successful launch."""
        registry = Mock(spec=CommandAdapterRegistry)
        mock_adapter = Mock()
        mock_adapter.entry.import_path = "vibe3.roles.plan"
        mock_adapter.callable = Mock(role_name="planner")
        registry.resolve.return_value = mock_adapter

        executor = JobExecutor(registry, mock_store)
        mock_lifecycle = Mock(spec=ExecutionLifecycleService)
        executor._lifecycle = mock_lifecycle

        with patch.object(executor, "_execute_issue_role") as mock_execute_role:
            mock_execute_role.return_value = ExecutionLaunchResult(
                launched=True,
                session_id="session-456",
                tmux_session="tmux-789",
                log_path="/path/to/log",
            )

            result = executor.execute(test_envelope)

        assert result.status == "launched"
        assert result.command_type == CommandType.PLAN
        assert result.issue_number == 123
        assert result.branch == "task/issue-123-test"
        assert result.context is not None
        assert result.context.session_id == "session-456"
        assert result.context.tmux_session == "tmux-789"

    def test_execute_returns_failed_on_adapter_error(
        self, mock_store: SQLiteClient, test_envelope: JobEnvelope
    ) -> None:
        """Executor should return failed result when adapter resolution fails."""
        registry = Mock(spec=CommandAdapterRegistry)
        registry.resolve.side_effect = Exception("Adapter not found")

        executor = JobExecutor(registry, mock_store)

        result = executor.execute(test_envelope)

        assert result.status == "failed"
        assert "Adapter resolution failed" in result.error_message
        assert result.error_code == "ADAPTER_RESOLUTION_ERROR"

    def test_execute_returns_skipped_result(
        self, mock_store: SQLiteClient, test_envelope: JobEnvelope
    ) -> None:
        """Executor should return skipped result when launch is skipped."""
        registry = Mock(spec=CommandAdapterRegistry)
        mock_adapter = Mock()
        mock_adapter.entry.import_path = "vibe3.roles.plan"
        mock_adapter.callable = Mock(role_name="planner")
        registry.resolve.return_value = mock_adapter

        executor = JobExecutor(registry, mock_store)
        mock_lifecycle = Mock(spec=ExecutionLifecycleService)
        executor._lifecycle = mock_lifecycle

        with patch.object(executor, "_execute_issue_role") as mock_execute_role:
            mock_execute_role.return_value = ExecutionLaunchResult(
                launched=False, skipped=True, reason="Capacity full"
            )

            result = executor.execute(test_envelope)

        assert result.status == "skipped"
        # Should record completed lifecycle (not failed)
        mock_lifecycle.record_completed.assert_called()

    def test_execute_handles_exception(
        self, mock_store: SQLiteClient, test_envelope: JobEnvelope
    ) -> None:
        """Executor should handle exceptions and return failed result."""
        registry = Mock(spec=CommandAdapterRegistry)
        mock_adapter = Mock()
        mock_adapter.entry.import_path = "vibe3.roles.plan"
        mock_adapter.callable = Mock(role_name="planner")
        registry.resolve.return_value = mock_adapter

        executor = JobExecutor(registry, mock_store)
        mock_lifecycle = Mock(spec=ExecutionLifecycleService)
        executor._lifecycle = mock_lifecycle

        with patch.object(executor, "_execute_issue_role") as mock_execute_role:
            mock_execute_role.side_effect = RuntimeError("Execution failed")

            result = executor.execute(test_envelope)

        assert result.status == "failed"
        assert "Execution failed" in result.error_message
        assert result.error_code == "EXECUTION_ERROR"
        # Should record failed lifecycle
        mock_lifecycle.record_failed.assert_called()


class TestMapLaunchResult:
    """Tests for _map_launch_result method."""

    def test_map_launch_result_launched(self, mock_store: SQLiteClient) -> None:
        """Launched result should map to 'launched' status."""
        registry = CommandAdapterRegistry()
        executor = JobExecutor(registry, mock_store)

        envelope = JobEnvelope(
            command_type=CommandType.PLAN,
            issue_number=123,
            branch="test-branch",
            source="cli-manual",
        )

        # Create a proper JobContext instead of Mock
        context = JobContext(
            issue_number=123,
            branch="test-branch",
            tmux_session="tmux-old",
            session_id="session-old",
            log_path="/old/path",
            worktree_path=None,
            cwd="/cwd",
            repo_path="/repo",
            mode="async",
        )
        launch_result = ExecutionLaunchResult(
            launched=True,
            session_id="session-123",
            tmux_session="tmux-456",
            log_path="/path/to/log",
        )

        result = executor._map_launch_result(launch_result, envelope, context)

        assert result.status == "launched"
        assert result.context is not None
        assert result.context.session_id == "session-123"
        assert result.context.tmux_session == "tmux-456"

    def test_map_launch_result_skipped(self, mock_store: SQLiteClient) -> None:
        """Skipped result should map to 'skipped' status."""
        registry = CommandAdapterRegistry()
        executor = JobExecutor(registry, mock_store)

        envelope = JobEnvelope(
            command_type=CommandType.PLAN,
            issue_number=123,
            branch="test-branch",
            source="cli-manual",
        )

        context = JobContext(
            issue_number=123,
            branch="test-branch",
        )
        launch_result = ExecutionLaunchResult(
            launched=False,
            skipped=True,
            reason="Capacity full",
        )

        result = executor._map_launch_result(launch_result, envelope, context)

        assert result.status == "skipped"

    def test_map_launch_result_failed(self, mock_store: SQLiteClient) -> None:
        """Failed launch should map to 'failed' status with error."""
        registry = CommandAdapterRegistry()
        executor = JobExecutor(registry, mock_store)

        envelope = JobEnvelope(
            command_type=CommandType.PLAN,
            issue_number=123,
            branch="test-branch",
            source="cli-manual",
        )

        context = JobContext(
            issue_number=123,
            branch="test-branch",
        )
        launch_result = ExecutionLaunchResult(
            launched=False,
            skipped=False,
            reason="Execution failed",
            reason_code="DISPATCH_ERROR",
        )

        result = executor._map_launch_result(launch_result, envelope, context)

        assert result.status == "failed"
        assert result.error_message == "Execution failed"
        assert result.error_code == "DISPATCH_ERROR"

    def test_map_launch_result_copies_metadata(self, mock_store: SQLiteClient) -> None:
        """Metadata from launch result should be copied to context."""
        registry = CommandAdapterRegistry()
        executor = JobExecutor(registry, mock_store)

        envelope = JobEnvelope(
            command_type=CommandType.PLAN,
            issue_number=123,
            branch="test-branch",
            source="cli-manual",
        )

        context = JobContext(
            issue_number=123,
            branch="test-branch",
            tmux_session=None,
            session_id=None,
            log_path=None,
            worktree_path=None,
            cwd="/cwd",
            repo_path="/repo",
            mode="async",
        )

        launch_result = ExecutionLaunchResult(
            launched=True,
            session_id="session-123",
            tmux_session="tmux-456",
            log_path="/path/to/log",
        )

        result = executor._map_launch_result(launch_result, envelope, context)

        assert result.context is not None
        assert result.context.session_id == "session-123"
        assert result.context.tmux_session == "tmux-456"
        assert result.context.log_path == "/path/to/log"


class TestVersionHashComputation:
    """Tests for version hash computation helpers."""

    def test_adapter_hash_computed_from_module_source(
        self, mock_store: SQLiteClient, tmp_path
    ) -> None:
        """Adapter hash should be computed from module source file."""
        import hashlib
        import importlib
        import sys
        from types import SimpleNamespace

        # Create a temporary module file
        module_dir = tmp_path / "test_module"
        module_dir.mkdir()
        module_file = module_dir / "adapter.py"
        module_content = "# Test adapter module\nprint('hello')\n"
        module_file.write_text(module_content)

        sys.path.insert(0, str(tmp_path))
        try:
            importlib.import_module("test_module.adapter")
            mock_resolved = SimpleNamespace(module_name="test_module.adapter")

            registry = CommandAdapterRegistry()
            executor = JobExecutor(registry, mock_store)
            adapter_hash = executor._compute_adapter_hash(mock_resolved)

            expected_hash = hashlib.sha256(module_content.encode("utf-8")).hexdigest()[
                :16
            ]
            assert adapter_hash == expected_hash
        finally:
            sys.modules.pop("test_module.adapter", None)
            sys.modules.pop("test_module", None)
            sys.path.remove(str(tmp_path))

    def test_policy_hash_aggregates_all_policy_files(self, tmp_path) -> None:
        """Policy hash should aggregate all policy files."""
        from vibe3.services import policy_loader
        from vibe3.utils import compute_hash_from_loader

        policy_dir = tmp_path / ".vibe" / "governance" / "policies"
        policy_dir.mkdir(parents=True)

        (policy_dir / "policy1.yaml").write_text("name: policy1\nversion: '1.0'\n")
        (policy_dir / "policy2.yaml").write_text("name: policy2\nversion: '2.0'\n")

        policy_hash = compute_hash_from_loader(policy_loader, policy_dir)

        assert policy_hash is not None
        assert len(policy_hash) == 16

    def test_material_hash_aggregates_all_material_files(self, tmp_path) -> None:
        """Material hash should aggregate all material files."""
        from vibe3.services import material_loader
        from vibe3.utils import compute_hash_from_loader

        material_dir = tmp_path / ".vibe" / "governance" / "materials"
        material_dir.mkdir(parents=True)

        (material_dir / "material1.md").write_text("# Material 1\nContent 1\n")
        (material_dir / "material2.md").write_text("# Material 2\nContent 2\n")

        material_hash = compute_hash_from_loader(material_loader, material_dir)

        assert material_hash is not None
        assert len(material_hash) == 16

    def test_hash_none_when_directory_missing(self, tmp_path) -> None:
        """Hash should return None when directory is missing."""
        from vibe3.services import material_loader, policy_loader
        from vibe3.utils import compute_hash_from_loader

        policy_hash = compute_hash_from_loader(policy_loader, tmp_path / "nonexistent")
        material_hash = compute_hash_from_loader(
            material_loader, tmp_path / "nonexistent"
        )

        assert policy_hash is None
        assert material_hash is None

    def test_hash_changes_when_file_changes(self, tmp_path) -> None:
        """Hash should change when file content changes."""
        from vibe3.services import policy_loader
        from vibe3.utils import compute_hash_from_loader

        policy_dir = tmp_path / ".vibe" / "governance" / "policies"
        policy_dir.mkdir(parents=True)

        policy1 = policy_dir / "policy1.yaml"
        policy1.write_text("name: policy1\nversion: '1.0'\n")

        hash1 = compute_hash_from_loader(policy_loader, policy_dir)

        policy1.write_text("name: policy1\nversion: '2.0'\n")
        hash2 = compute_hash_from_loader(policy_loader, policy_dir)

        assert hash1 != hash2

    def test_adapter_hash_none_when_module_file_missing(
        self, mock_store: SQLiteClient
    ) -> None:
        """Adapter hash should return None when module.__file__ is None."""
        from types import SimpleNamespace

        registry = CommandAdapterRegistry()
        executor = JobExecutor(registry, mock_store)

        mock_resolved = SimpleNamespace(module_name="namespace_package")
        mock_module = Mock()
        mock_module.__file__ = None

        with patch("importlib.import_module", return_value=mock_module):
            adapter_hash = executor._compute_adapter_hash(mock_resolved)

        assert adapter_hash is None
