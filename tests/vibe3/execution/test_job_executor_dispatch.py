"""Tests for JobExecutor dispatch logic."""

from unittest.mock import Mock, patch

import pytest

from vibe3.clients import SQLiteClient
from vibe3.execution.command_adapter import CommandAdapterRegistry
from vibe3.execution.execution_lifecycle import ExecutionLifecycleService
from vibe3.execution.job_executor import JobExecutor
from vibe3.models.execution_request import ExecutionLaunchResult
from vibe3.models.job import CommandType, JobEnvelope


@pytest.fixture
def mock_store() -> SQLiteClient:
    """Mock SQLite client."""
    return Mock(spec=SQLiteClient)


@pytest.fixture
def mock_lifecycle() -> ExecutionLifecycleService:
    """Mock execution lifecycle service."""
    mock = Mock(spec=ExecutionLifecycleService)
    return mock


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
