"""Tests for JobExecutor service."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

from vibe3.execution.command_adapter import CommandAdapterEntry, ResolvedAdapter
from vibe3.execution.job_executor import (
    COMMAND_TYPE_TO_EXECUTION_ROLE,
    JobExecutor,
)
from vibe3.models.execution_request import ExecutionLaunchResult
from vibe3.models.job import CommandType, JobEnvelope

if TYPE_CHECKING:
    pass


class TestMappingCorrectness:
    """Test 1: Verify all CommandType values map correctly."""

    def test_command_type_to_execution_role_mapping(self) -> None:
        """All 6 CommandType values should map to correct ExecutionRole."""
        expected_mappings = {
            CommandType.PLAN: "planner",
            CommandType.RUN: "executor",
            CommandType.REVIEW: "reviewer",
            CommandType.MANAGER: "manager",
            CommandType.GOVERNANCE_SCAN: "governance",
            CommandType.SUPERVISOR_APPLY: "supervisor",
        }

        assert COMMAND_TYPE_TO_EXECUTION_ROLE == expected_mappings

        # Verify all CommandType values are covered
        all_command_types = list(CommandType)
        assert len(COMMAND_TYPE_TO_EXECUTION_ROLE) == len(all_command_types)
        for ct in all_command_types:
            assert ct in COMMAND_TYPE_TO_EXECUTION_ROLE


class TestContextBuilding:
    """Test 2: Verify _build_context() populates fields from envelope and env."""

    def test_build_context_populates_basic_fields(self) -> None:
        """Context should contain issue_number, branch, and environment metadata."""
        # Setup
        envelope = JobEnvelope(
            command_type=CommandType.PLAN,
            issue_number=123,
            branch="test-branch",
            source="cli-manual",
        )

        registry = Mock()
        store = Mock()
        executor = JobExecutor(registry, store)

        # Mock environment
        with patch.dict(os.environ, {"TMUX": "/tmp/tmux-123"}, clear=False):
            with patch(
                "vibe3.execution.job_executor.resolve_orchestra_repo_root"
            ) as mock_repo:
                mock_repo.return_value = Mock(
                    worktree="/path/to/worktree",
                    repo="/path/to/repo",
                )

                context = executor._build_context(envelope)

        # Verify basic fields
        assert context.issue_number == 123
        assert context.branch == "test-branch"
        assert context.tmux_session is not None
        assert context.cwd is not None

    def test_build_context_handles_missing_tmux(self) -> None:
        """Context should handle missing TMUX environment."""
        envelope = JobEnvelope(
            command_type=CommandType.RUN,
            issue_number=456,
            branch="test-branch-2",
            source="heartbeat-tick",
        )

        registry = Mock()
        store = Mock()
        executor = JobExecutor(registry, store)

        # Clear TMUX env
        with patch.dict(os.environ, {}, clear=True):
            if "TMUX" in os.environ:
                del os.environ["TMUX"]
            if "TMUX_PANE" in os.environ:
                del os.environ["TMUX_PANE"]

            with patch(
                "vibe3.execution.job_executor.resolve_orchestra_repo_root"
            ) as mock_repo:
                mock_repo.return_value = Mock(
                    worktree="/path/to/worktree", repo="/path/to/repo"
                )

                context = executor._build_context(envelope)

        assert context.issue_number == 456
        # tmux_session should be None when no TMUX env


class TestSuccessPath:
    """Test 3: Mock runner to return launched result."""

    def test_execute_returns_launched_result(self) -> None:
        """Successful issue role execution should return launched JobResult."""
        # Setup envelope
        envelope = JobEnvelope(
            command_type=CommandType.PLAN,
            issue_number=789,
            branch="success-test",
            source="cli-manual",
        )

        # Setup mock registry
        mock_spec = Mock()
        mock_spec.role_name = "planner"  # IssueRoleSyncSpec marker

        mock_entry = CommandAdapterEntry(
            job_type=CommandType.PLAN,
            import_path="vibe3.roles.plan",
            callable_name="build_plan_async_request",
            description="Plan executor",
        )

        mock_resolved = ResolvedAdapter(
            entry=mock_entry,
            callable=mock_spec,
            module_name="vibe3.roles.plan",
            qualname="build_plan_async_request",
        )

        registry = Mock()
        registry.resolve = Mock(return_value=mock_resolved)

        # Mock SQLiteClient to return empty list for live sessions
        store = Mock()
        store.list_live_runtime_sessions = Mock(return_value=[])
        store.insert_runtime_session = Mock()
        store.update_runtime_session = Mock()

        executor = JobExecutor(registry, store)

        # Mock execution path
        mock_launch_result = ExecutionLaunchResult(
            launched=True,
            skipped=False,
            session_id="test-session-123",
            tmux_session="tmux-test",
            log_path="logs/test.log",
        )

        with patch.object(
            executor, "_execute_issue_role", return_value=mock_launch_result
        ):
            result = executor.execute(envelope)

        # Verify result
        assert result.status == "launched"
        assert result.command_type == CommandType.PLAN
        assert result.issue_number == 789
        assert result.branch == "success-test"
        assert result.adapter_path == "vibe3.roles.plan"

        # Verify context metadata
        assert result.context is not None
        assert result.context.session_id == "test-session-123"
        assert result.context.tmux_session == "tmux-test"
        assert result.context.log_path == "logs/test.log"


class TestFailurePath:
    """Test 4: Mock runner to raise exception."""

    def test_execute_returns_failed_on_exception(self) -> None:
        """Execution exception should return failed JobResult with error."""
        envelope = JobEnvelope(
            command_type=CommandType.RUN,
            issue_number=999,
            branch="failure-test",
            source="cli-manual",
        )

        # Setup mock registry
        mock_spec = Mock()
        mock_spec.role_name = "executor"

        mock_entry = CommandAdapterEntry(
            job_type=CommandType.RUN,
            import_path="vibe3.roles.run",
            callable_name="build_run_async_request",
            description="Run executor",
        )

        mock_resolved = ResolvedAdapter(
            entry=mock_entry,
            callable=mock_spec,
            module_name="vibe3.roles.run",
            qualname="build_run_async_request",
        )

        registry = Mock()
        registry.resolve = Mock(return_value=mock_resolved)

        # Mock SQLiteClient to return empty list for live sessions
        store = Mock()
        store.list_live_runtime_sessions = Mock(return_value=[])
        store.insert_runtime_session = Mock()
        store.update_runtime_session = Mock()

        executor = JobExecutor(registry, store)

        # Mock execution to raise exception
        with patch.object(
            executor,
            "_execute_issue_role",
            side_effect=RuntimeError("Execution failed"),
        ):
            result = executor.execute(envelope)

        # Verify result
        assert result.status == "failed"
        assert result.error_message == "Execution failed"
        assert result.error_code == "EXECUTION_ERROR"


class TestSkipPath:
    """Test 5: Mock ExecutionLaunchResult with skipped=True."""

    def test_execute_returns_skipped_result(self) -> None:
        """Skipped execution should return skipped JobResult."""
        envelope = JobEnvelope(
            command_type=CommandType.REVIEW,
            issue_number=555,
            branch="skip-test",
            source="heartbeat-tick",
        )

        # Setup mock registry
        mock_spec = Mock()
        mock_spec.role_name = "reviewer"

        mock_entry = CommandAdapterEntry(
            job_type=CommandType.REVIEW,
            import_path="vibe3.roles.review",
            callable_name="build_review_async_request",
            description="Review executor",
        )

        mock_resolved = ResolvedAdapter(
            entry=mock_entry,
            callable=mock_spec,
            module_name="vibe3.roles.review",
            qualname="build_review_async_request",
        )

        registry = Mock()
        registry.resolve = Mock(return_value=mock_resolved)

        # Mock SQLiteClient to return empty list for live sessions
        store = Mock()
        store.list_live_runtime_sessions = Mock(return_value=[])
        store.insert_runtime_session = Mock()
        store.update_runtime_session = Mock()

        executor = JobExecutor(registry, store)

        # Mock execution to return skipped
        mock_launch_result = ExecutionLaunchResult(
            launched=False,
            skipped=True,
            reason="No changes to review",
            reason_code="NO_CHANGES",
        )

        with patch.object(
            executor, "_execute_issue_role", return_value=mock_launch_result
        ):
            result = executor.execute(envelope)

        # Verify result
        assert result.status == "skipped"
        assert result.command_type == CommandType.REVIEW


class TestGovernanceDispatch:
    """Test 6: Verify governance command type routes correctly."""

    def test_governance_routes_to_execute_governance(self) -> None:
        """GOVERNANCE_SCAN should dispatch to _execute_governance."""
        envelope = JobEnvelope(
            command_type=CommandType.GOVERNANCE_SCAN,
            issue_number=0,  # Governance has no issue
            branch="governance-test",
            source="heartbeat-tick",
        )

        # Setup mock registry
        mock_entry = CommandAdapterEntry(
            job_type=CommandType.GOVERNANCE_SCAN,
            import_path="vibe3.roles.governance",
            callable_name="run_governance_sync",
            description="Governance scanner",
        )

        mock_resolved = ResolvedAdapter(
            entry=mock_entry,
            callable=Mock(),  # Governance doesn't use IssueRoleSyncSpec
            module_name="vibe3.roles.governance",
            qualname="run_governance_sync",
        )

        registry = Mock()
        registry.resolve = Mock(return_value=mock_resolved)

        # Mock SQLiteClient to return empty list for live sessions
        store = Mock()
        store.list_live_runtime_sessions = Mock(return_value=[])
        store.insert_runtime_session = Mock()
        store.update_runtime_session = Mock()

        executor = JobExecutor(registry, store)

        result = executor.execute(envelope)

        # Governance is stubbed, should return skipped
        assert result.status == "skipped"
        assert result.error_message == "Governance execution not implemented in MVP"
        assert result.error_code == "NOT_IMPLEMENTED"


class TestEquivalenceRegression:
    """Test 7: Verify CLI and server execution produce equivalent results."""

    def test_cli_and_server_produce_equivalent_results(self) -> None:
        """Same command with different source should produce equivalent JobResult."""
        # CLI-driven envelope
        cli_envelope = JobEnvelope(
            command_type=CommandType.PLAN,
            issue_number=123,
            branch="equivalence-test",
            source="cli-manual",
            actor="human:cli",
        )

        # Server-driven envelope
        server_envelope = JobEnvelope(
            command_type=CommandType.PLAN,
            issue_number=123,
            branch="equivalence-test",
            source="heartbeat-tick",
            actor="orchestra:system",
        )

        # Setup mock registry
        mock_spec = Mock()
        mock_spec.role_name = "planner"

        mock_entry = CommandAdapterEntry(
            job_type=CommandType.PLAN,
            import_path="vibe3.roles.plan",
            callable_name="build_plan_async_request",
            description="Plan executor",
        )

        mock_resolved = ResolvedAdapter(
            entry=mock_entry,
            callable=mock_spec,
            module_name="vibe3.roles.plan",
            qualname="build_plan_async_request",
        )

        registry = Mock()
        registry.resolve = Mock(return_value=mock_resolved)

        # Mock SQLiteClient to return empty list for live sessions
        store = Mock()
        store.list_live_runtime_sessions = Mock(return_value=[])
        store.insert_runtime_session = Mock()
        store.update_runtime_session = Mock()

        executor = JobExecutor(registry, store)

        # Mock same execution result for both
        mock_launch_result = ExecutionLaunchResult(
            launched=True,
            skipped=False,
            session_id="equivalence-session",
            tmux_session="equivalence-tmux",
            log_path="logs/equivalence.log",
        )

        with patch.object(
            executor, "_execute_issue_role", return_value=mock_launch_result
        ):
            cli_result = executor.execute(cli_envelope)
            server_result = executor.execute(server_envelope)

        # Verify equivalence (except source field)
        assert cli_result.status == server_result.status
        assert cli_result.command_type == server_result.command_type
        assert cli_result.issue_number == server_result.issue_number
        assert cli_result.branch == server_result.branch

        # Context metadata should be equivalent
        assert cli_result.context.session_id == server_result.context.session_id
        assert cli_result.context.tmux_session == server_result.context.tmux_session
        assert cli_result.context.log_path == server_result.context.log_path

        # Only source should differ
        assert cli_result.source == "cli-manual"
        assert server_result.source == "heartbeat-tick"


class TestLifecycleEventRecording:
    """Test 8: Verify lifecycle events are recorded correctly."""

    def test_lifecycle_started_and_completed_recorded(self) -> None:
        """Executor should record started and completed lifecycle events."""
        envelope = JobEnvelope(
            command_type=CommandType.RUN,
            issue_number=111,
            branch="lifecycle-test",
            source="cli-manual",
        )

        # Setup mock registry
        mock_spec = Mock()
        mock_spec.role_name = "executor"

        mock_entry = CommandAdapterEntry(
            job_type=CommandType.RUN,
            import_path="vibe3.roles.run",
            callable_name="build_run_async_request",
            description="Run executor",
        )

        mock_resolved = ResolvedAdapter(
            entry=mock_entry,
            callable=mock_spec,
            module_name="vibe3.roles.run",
            qualname="build_run_async_request",
        )

        registry = Mock()
        registry.resolve = Mock(return_value=mock_resolved)

        # Mock lifecycle service
        store = Mock()
        lifecycle_mock = Mock()
        lifecycle_mock.record_started = Mock()
        lifecycle_mock.record_completed = Mock()

        executor = JobExecutor(registry, store)
        executor._lifecycle = lifecycle_mock

        # Mock execution
        mock_launch_result = ExecutionLaunchResult(
            launched=True,
            skipped=False,
        )

        with patch.object(
            executor, "_execute_issue_role", return_value=mock_launch_result
        ):
            executor.execute(envelope)

        # Verify lifecycle calls
        lifecycle_mock.record_started.assert_called_once()
        lifecycle_mock.record_completed.assert_called_once()

        # Verify role mapping
        started_call = lifecycle_mock.record_started.call_args
        assert started_call[1]["role"] == "executor"
        assert started_call[1]["target"] == "lifecycle-test"


class TestAdapterResolutionError:
    """Test 9: Unregistered command type should fail."""

    def test_unregistered_command_type_returns_failed(self) -> None:
        """Unregistered command type should return failed JobResult."""
        envelope = JobEnvelope(
            command_type=CommandType.MANAGER,
            issue_number=333,
            branch="adapter-error-test",
            source="heartbeat-tick",
        )

        # Setup registry to raise error
        registry = Mock()
        registry.resolve = Mock(side_effect=ValueError("Command type not registered"))

        store = Mock()
        executor = JobExecutor(registry, store)

        result = executor.execute(envelope)

        # Verify result
        assert result.status == "failed"
        assert "Adapter resolution failed" in result.error_message
        assert result.error_code == "ADAPTER_RESOLUTION_ERROR"
