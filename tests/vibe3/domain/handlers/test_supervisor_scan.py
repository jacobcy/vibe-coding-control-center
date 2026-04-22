"""Tests for supervisor scan domain event handler."""

from unittest.mock import MagicMock, patch

from vibe3.domain.events.supervisor_apply import SupervisorIssueIdentified
from vibe3.execution.contracts import ExecutionLaunchResult


class TestSupervisorScanHandler:
    """supervisor_scan handler dispatches supervisor apply via coordinator."""

    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.supervisor_scan.load_orchestra_config")
    @patch("vibe3.roles.supervisor.build_supervisor_apply_request")
    def test_normal_dispatch(
        self,
        mock_build_request: MagicMock,
        mock_from_settings: MagicMock,
        mock_coordinator_cls: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.supervisor_scan import (
            handle_supervisor_issue_identified,
        )

        mock_config = MagicMock(dry_run=False)
        mock_from_settings.return_value = mock_config

        mock_request = MagicMock()
        mock_build_request.return_value = mock_request

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

        mock_build_request.assert_called_once_with(
            mock_config,
            42,
            issue_title="Test governance issue",
        )
        mock_coordinator.dispatch_execution.assert_called_once_with(mock_request)

    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.supervisor_scan.load_orchestra_config")
    def test_dry_run_skips_dispatch(
        self,
        mock_from_settings: MagicMock,
        mock_coordinator_cls: MagicMock,
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

        mock_coordinator_cls.assert_not_called()

    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.supervisor_scan.load_orchestra_config")
    @patch("vibe3.roles.supervisor.build_supervisor_apply_request")
    def test_dispatch_failure_logged(
        self,
        mock_build_request: MagicMock,
        mock_from_settings: MagicMock,
        mock_coordinator_cls: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.supervisor_scan import (
            handle_supervisor_issue_identified,
        )

        mock_config = MagicMock(dry_run=False)
        mock_from_settings.return_value = mock_config

        mock_request = MagicMock()
        mock_build_request.return_value = mock_request

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

    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.supervisor_scan.load_orchestra_config")
    @patch("vibe3.roles.supervisor.build_supervisor_apply_request")
    def test_exception_during_build_logged(
        self,
        mock_build_request: MagicMock,
        mock_from_settings: MagicMock,
        mock_coordinator_cls: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.supervisor_scan import (
            handle_supervisor_issue_identified,
        )

        mock_config = MagicMock(dry_run=False)
        mock_from_settings.return_value = mock_config

        mock_build_request.side_effect = RuntimeError("build failed")

        handle_supervisor_issue_identified(
            SupervisorIssueIdentified(
                issue_number=42,
                issue_title="Test governance issue",
                supervisor_file="supervisor.md",
            )
        )
