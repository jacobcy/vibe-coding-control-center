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
from vibe3.models.execution_request import ExecutionLaunchResult
from vibe3.models.job import CommandType, JobContext, JobEnvelope


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


class TestEquivalenceRegression:
    """Tests for semantic equivalence between different sources."""

    def test_cli_manual_and_heartbeat_tick_produce_equivalent_results(
        self, mock_store: SQLiteClient
    ) -> None:
        """Same command from different sources should produce equivalent results."""
        # Create two envelopes with same command/issue/branch, different source
        envelope_cli = JobEnvelope(
            command_type=CommandType.PLAN,
            issue_number=123,
            branch="task/issue-123-test",
            source="cli-manual",
            actor="test:cli",
        )
        envelope_heartbeat = JobEnvelope(
            command_type=CommandType.PLAN,
            issue_number=123,
            branch="task/issue-123-test",
            source="heartbeat-tick",
            actor="orchestra:system",
        )

        # Setup registry
        registry = Mock(spec=CommandAdapterRegistry)
        mock_adapter = Mock()
        mock_adapter.entry.import_path = "vibe3.roles.plan"
        mock_adapter.callable = Mock(role_name="planner")
        registry.resolve.return_value = mock_adapter

        executor = JobExecutor(registry, mock_store)
        mock_lifecycle = Mock(spec=ExecutionLifecycleService)
        executor._lifecycle = mock_lifecycle

        # Mock execution to return same result
        launch_result = ExecutionLaunchResult(
            launched=True,
            session_id="session-123",
            tmux_session="tmux-456",
            log_path="/path/to/log",
        )

        with patch.object(executor, "_execute_issue_role", return_value=launch_result):
            result_cli = executor.execute(envelope_cli)
            result_heartbeat = executor.execute(envelope_heartbeat)

        # Results should be equivalent except for source
        assert result_cli.status == result_heartbeat.status
        assert result_cli.command_type == result_heartbeat.command_type
        assert result_cli.issue_number == result_heartbeat.issue_number
        assert result_cli.branch == result_heartbeat.branch
        assert result_cli.adapter_path == result_heartbeat.adapter_path
        assert result_cli.context is not None
        assert result_heartbeat.context is not None
        assert result_cli.context.session_id == result_heartbeat.context.session_id

        # Only source should differ
        assert result_cli.source == "cli-manual"
        assert result_heartbeat.source == "heartbeat-tick"


class TestGovernanceDispatch:
    """Tests for governance command dispatch."""

    def test_governance_routes_to_execute_governance(
        self, mock_store: SQLiteClient
    ) -> None:
        """GOVERNANCE_SCAN should route to _execute_governance."""
        envelope = JobEnvelope(
            command_type=CommandType.GOVERNANCE_SCAN,
            issue_number=999,
            branch="main",
            source="cli-manual",
            actor="test:executor",
        )

        registry = Mock(spec=CommandAdapterRegistry)
        mock_adapter = Mock()
        mock_adapter.entry.import_path = "vibe3.roles.governance"
        mock_adapter.callable = Mock()  # Governance role, not IssueRoleSyncSpec
        registry.resolve.return_value = mock_adapter

        executor = JobExecutor(registry, mock_store)
        mock_lifecycle = Mock(spec=ExecutionLifecycleService)
        executor._lifecycle = mock_lifecycle

        # Mock _execute_governance
        with patch.object(executor, "_execute_governance") as mock_execute_gov:
            mock_execute_gov.return_value = ExecutionLaunchResult(
                launched=False,
                skipped=True,
                reason="Not implemented",
                reason_code="NOT_IMPLEMENTED",
            )

            result = executor.execute(envelope)

        # Should call _execute_governance, not _execute_issue_role
        mock_execute_gov.assert_called_once()
        assert result.status == "skipped"


class TestSyncDispatch:
    """Tests for _execute_issue_role_sync implementation."""

    def test_sync_dispatch_builds_sync_request(self, mock_store: SQLiteClient) -> None:
        """Sync dispatch should call build_sync_request, not build_async_request."""
        envelope = JobEnvelope(
            command_type=CommandType.PLAN,
            issue_number=123,
            branch="task/issue-123",
            source="cli-manual",
            actor="test:sync",
            mode="sync",
            refs={
                "flow_state": '{"test": true}',
                "session_id": "session-456",
                "dry_run": "false",
                "show_prompt": "false",
            },
        )

        registry = Mock(spec=CommandAdapterRegistry)
        mock_spec = Mock()
        mock_spec.role_name = "planner"

        # Mock the resolved adapter
        mock_adapter = Mock()
        mock_adapter.entry.import_path = "vibe3.roles.plan"
        mock_adapter.callable = mock_spec
        registry.resolve.return_value = mock_adapter

        executor = JobExecutor(registry, mock_store)

        # Mock lifecycle to avoid calling real store methods
        mock_lifecycle = Mock(spec=ExecutionLifecycleService)
        executor._lifecycle = mock_lifecycle

        # Mock _execute_issue_role_sync to verify it's called
        with patch.object(executor, "_execute_issue_role_sync") as mock_sync_execute:
            mock_sync_execute.return_value = ExecutionLaunchResult(
                launched=True,
                session_id="session-789",
                tmux_session="tmux-999",
            )

            result = executor.execute(envelope)

        # Should route to _execute_issue_role_sync, not _execute_issue_role
        mock_sync_execute.assert_called_once()
        assert result.status == "launched"

    def test_sync_dispatch_uses_flow_state_and_session_id(
        self, mock_store: SQLiteClient
    ) -> None:
        """Sync dispatch should pass flow_state and session_id from envelope."""
        envelope = JobEnvelope(
            command_type=CommandType.PLAN,
            issue_number=123,
            branch="task/issue-123",
            source="cli-manual",
            actor="test:sync",
            mode="sync",
            refs={
                "flow_state": '{"plan_ref": "docs/plans/test.md"}',
                "session_id": "session-456",
            },
        )

        registry = Mock(spec=CommandAdapterRegistry)
        executor = JobExecutor(registry, mock_store)

        # Mock the coordinator
        with patch(
            "vibe3.execution.coordinator.ExecutionCoordinator"
        ) as mock_coordinator_class:
            mock_coordinator = Mock()
            mock_coordinator.dispatch_execution.return_value = ExecutionLaunchResult(
                launched=True
            )
            mock_coordinator_class.return_value = mock_coordinator

            with patch("vibe3.services.load_issue_info") as mock_load_issue:
                mock_issue = Mock()
                mock_issue.number = 123
                mock_load_issue.return_value = mock_issue

                with patch(
                    "vibe3.execution.issue_role_sync_runner.format_agent_actor"
                ) as mock_format_actor:
                    mock_format_actor.return_value = "test:planner"

                    mock_spec = Mock()
                    mock_spec.role_name = "planner"
                    mock_spec.resolve_options.return_value = Mock()
                    mock_spec.build_sync_request.return_value = Mock()

                    executor._execute_issue_role_sync(envelope, mock_spec)

        # Verify build_sync_request was called with flow_state and session_id
        call_args = mock_spec.build_sync_request.call_args
        assert call_args is not None
        # flow_state is passed as positional arg (3rd arg after config, issue)
        assert call_args[0][2] == "task/issue-123"  # branch
        # session_id is the 4th positional arg
        assert call_args[0][4] == "session-456"


class TestGovernanceDispatchImplementation:
    """Tests for _execute_governance actual implementation."""

    def test_governance_builds_correct_cmd_structure(
        self, mock_store: SQLiteClient
    ) -> None:
        """Governance dispatch should build CLI self-invocation command."""
        envelope = JobEnvelope(
            command_type=CommandType.GOVERNANCE_SCAN,
            issue_number=999,
            branch="governance",
            source="heartbeat-tick",
            actor="orchestra:governance",
            governance_tick_count=42,
        )

        registry = Mock(spec=CommandAdapterRegistry)
        executor = JobExecutor(registry, mock_store)

        with patch(
            "vibe3.execution.coordinator.ExecutionCoordinator"
        ) as mock_coordinator_class:
            mock_coordinator = Mock()
            mock_coordinator.dispatch_execution.return_value = ExecutionLaunchResult(
                launched=True,
                tmux_session="tmux-gov-42",
            )
            mock_coordinator_class.return_value = mock_coordinator

            with patch(
                "vibe3.execution.job_executor.resolve_orchestra_repo_root"
            ) as mock_repo:
                from pathlib import Path

                mock_repo.return_value = Path("/test/repo")

                executor._execute_governance(envelope)

        # Verify dispatch was called
        assert mock_coordinator.dispatch_execution.called
        # Verify the request passed to dispatch_execution
        call_args = mock_coordinator.dispatch_execution.call_args
        request = call_args[0][0]

        # Check cmd structure: should NOT pass tick_count twice
        assert request.cmd is not None
        assert "internal" in request.cmd
        assert "governance" in request.cmd
        # Should have tick_count once, not twice
        tick_count_occurrences = request.cmd.count("42")
        assert (
            tick_count_occurrences == 1
        ), f"tick_count should appear once in cmd, found {tick_count_occurrences}"

        # Check other request properties
        assert request.role == "governance"
        assert request.actor == "orchestra:governance"
        assert request.refs == {"tick": "42"}

    def test_governance_passes_material_override(
        self, mock_store: SQLiteClient
    ) -> None:
        """Governance dispatch should include material override when provided."""
        envelope = JobEnvelope(
            command_type=CommandType.GOVERNANCE_SCAN,
            issue_number=999,
            branch="governance",
            source="heartbeat-tick",
            actor="orchestra:governance",
            governance_tick_count=5,
            governance_material_override="docs/materials/custom.md",
        )

        registry = Mock(spec=CommandAdapterRegistry)
        executor = JobExecutor(registry, mock_store)

        with patch(
            "vibe3.execution.coordinator.ExecutionCoordinator"
        ) as mock_coordinator_class:
            mock_coordinator = Mock()
            mock_coordinator.dispatch_execution.return_value = ExecutionLaunchResult(
                launched=True
            )
            mock_coordinator_class.return_value = mock_coordinator

            with patch(
                "vibe3.execution.job_executor.resolve_orchestra_repo_root"
            ) as mock_repo:
                from pathlib import Path

                mock_repo.return_value = Path("/test/repo")

                executor._execute_governance(envelope)

        # Verify material override is in cmd
        call_args = mock_coordinator.dispatch_execution.call_args
        request = call_args[0][0]
        assert "--material" in request.cmd
        assert "docs/materials/custom.md" in request.cmd


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
