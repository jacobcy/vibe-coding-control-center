"""Tests for supervisor scan domain event handler."""

from unittest.mock import MagicMock, patch

from vibe3.domain.events.supervisor_apply import SupervisorIssueIdentified
from vibe3.execution.contracts import ExecutionLaunchResult


class TestSupervisorScanHandler:
    """supervisor_scan handler dispatches supervisor apply via CLI self-invocation."""

    @patch("vibe3.orchestra.logging.append_orchestra_event")
    @patch("vibe3.clients.sqlite_client.SQLiteClient")
    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.supervisor_scan.load_orchestra_config")
    def test_normal_dispatch(
        self,
        mock_from_settings: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_sqlite_cls: MagicMock,
        mock_append_event: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.supervisor_scan import (
            handle_supervisor_issue_identified,
        )

        mock_config = MagicMock(dry_run=False)
        mock_from_settings.return_value = mock_config

        mock_coordinator = MagicMock()
        mock_coordinator.dispatch_execution.return_value = ExecutionLaunchResult(
            launched=True,
            tmux_session="vibe3-supervisor-42",
            log_path="/tmp/sup.log",
        )
        mock_coordinator_cls.return_value = mock_coordinator

        handle_supervisor_issue_identified(
            SupervisorIssueIdentified(
                issue_number=42,
                issue_title="Test governance issue",
                supervisor_file="supervisor.md",
            )
        )

        mock_coordinator.dispatch_execution.assert_called_once()
        # Verify CLI self-invocation command structure
        call_args = mock_coordinator.dispatch_execution.call_args.args[0]
        assert call_args.role == "supervisor"
        assert call_args.mode == "async"
        assert call_args.cmd is not None
        assert "internal" in call_args.cmd
        assert "apply" in call_args.cmd
        assert "42" in call_args.cmd  # issue_number
        assert "--no-async" in call_args.cmd

    @patch("vibe3.domain.handlers.supervisor_scan.load_orchestra_config")
    def test_dry_run_skips_dispatch(
        self,
        mock_from_settings: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.supervisor_scan import (
            handle_supervisor_issue_identified,
        )

        mock_config = MagicMock(dry_run=True)
        mock_from_settings.return_value = mock_config

        handle_supervisor_issue_identified(
            SupervisorIssueIdentified(
                issue_number=42,
                issue_title="Test governance issue",
                supervisor_file="supervisor.md",
            )
        )

    @patch("vibe3.orchestra.logging.append_orchestra_event")
    @patch("vibe3.clients.sqlite_client.SQLiteClient")
    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.supervisor_scan.load_orchestra_config")
    def test_dispatch_failure_logged(
        self,
        mock_from_settings: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_sqlite_cls: MagicMock,
        mock_append_event: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.supervisor_scan import (
            handle_supervisor_issue_identified,
        )

        mock_config = MagicMock(dry_run=False)
        mock_from_settings.return_value = mock_config

        mock_coordinator = MagicMock()
        mock_coordinator.dispatch_execution.return_value = ExecutionLaunchResult(
            launched=False, reason="capacity full", reason_code="capacity_full"
        )
        mock_coordinator_cls.return_value = mock_coordinator

        handle_supervisor_issue_identified(
            SupervisorIssueIdentified(
                issue_number=42,
                issue_title="Test governance issue",
                supervisor_file="supervisor.md",
            )
        )

        mock_coordinator.dispatch_execution.assert_called_once()

    @patch("vibe3.orchestra.logging.append_orchestra_event")
    @patch("vibe3.clients.sqlite_client.SQLiteClient")
    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.supervisor_scan.load_orchestra_config")
    def test_exception_during_dispatch_logged(
        self,
        mock_from_settings: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_sqlite_cls: MagicMock,
        mock_append_event: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.supervisor_scan import (
            handle_supervisor_issue_identified,
        )

        mock_config = MagicMock(dry_run=False)
        mock_from_settings.return_value = mock_config

        mock_coordinator = MagicMock()
        mock_coordinator.dispatch_execution.side_effect = RuntimeError(
            "dispatch failed"
        )
        mock_coordinator_cls.return_value = mock_coordinator

        handle_supervisor_issue_identified(
            SupervisorIssueIdentified(
                issue_number=42,
                issue_title="Test governance issue",
                supervisor_file="supervisor.md",
            )
        )

        mock_coordinator.dispatch_execution.assert_called_once()
