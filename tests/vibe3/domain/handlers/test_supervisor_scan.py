"""Tests for supervisor scan domain event handler."""

from unittest.mock import MagicMock, patch

from vibe3.models import ExecutionLaunchResult, SupervisorIssueIdentified


class TestSupervisorScanHandler:
    """supervisor_scan handler dispatches supervisor apply via CLI self-invocation."""

    @patch("vibe3.config.resolve_repo_agent_preset")
    @patch("vibe3.observability.orchestra_log.append_orchestra_event")
    @patch("vibe3.clients.sqlite_client.SQLiteClient")
    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.supervisor_scan.load_orchestra_config")
    def test_normal_dispatch(
        self,
        mock_from_settings: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_sqlite_cls: MagicMock,
        mock_append_event: MagicMock,
        mock_preset: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.supervisor_scan import (
            handle_supervisor_issue_identified,
        )

        mock_config = MagicMock(dry_run=False)
        mock_from_settings.return_value = mock_config

        mock_preset.return_value = ("openai", "gpt-4")

        mock_coordinator = MagicMock()
        mock_coordinator.dispatch_execution.return_value = ExecutionLaunchResult(
            launched=True,
            tmux_session="vibe3-supervisor-42",
            log_path="/tmp/sup.log",
        )
        mock_coordinator_cls.return_value = mock_coordinator

        result = handle_supervisor_issue_identified(
            SupervisorIssueIdentified(
                issue_number=42,
                issue_title="Test governance issue",
                supervisor_file="supervisor.md",
            )
        )

        assert result is not None
        assert result.launched is True
        assert result.tmux_session == "vibe3-supervisor-42"
        assert result.log_path == "/tmp/sup.log"
        assert result.backend == "openai"
        assert result.model == "gpt-4"
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

        result = handle_supervisor_issue_identified(
            SupervisorIssueIdentified(
                issue_number=42,
                issue_title="Test governance issue",
                supervisor_file="supervisor.md",
            )
        )
        assert result is None

    @patch("vibe3.config.resolve_repo_agent_preset")
    @patch("vibe3.domain.handlers.supervisor_scan.get_store")
    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.supervisor_scan.load_orchestra_config")
    def test_uses_injected_coordinator_without_lazy_creation(
        self,
        mock_from_settings: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_get_store: MagicMock,
        mock_preset: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.supervisor_scan import (
            handle_supervisor_issue_identified,
        )

        mock_config = MagicMock(dry_run=False)
        mock_from_settings.return_value = mock_config

        mock_preset.return_value = ("anthropic", "claude-3")

        injected_coordinator = MagicMock()
        injected_coordinator.dispatch_execution.return_value = ExecutionLaunchResult(
            launched=True,
            tmux_session="vibe3-supervisor-42",
            log_path="/tmp/sup.log",
        )

        result = handle_supervisor_issue_identified(
            SupervisorIssueIdentified(
                issue_number=42,
                issue_title="Test governance issue",
                supervisor_file="supervisor.md",
            ),
            coordinator=injected_coordinator,
        )

        assert result is not None
        assert result.launched is True
        assert result.tmux_session == "vibe3-supervisor-42"
        assert result.log_path == "/tmp/sup.log"
        assert result.backend == "anthropic"
        assert result.model == "claude-3"
        injected_coordinator.dispatch_execution.assert_called_once()
        mock_coordinator_cls.assert_not_called()
        mock_get_store.assert_not_called()

    @patch("vibe3.observability.orchestra_log.append_orchestra_event")
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

        result = handle_supervisor_issue_identified(
            SupervisorIssueIdentified(
                issue_number=42,
                issue_title="Test governance issue",
                supervisor_file="supervisor.md",
            )
        )

        assert result is not None
        assert result.launched is False
        assert result.reason == "capacity full"
        mock_coordinator.dispatch_execution.assert_called_once()

    @patch("vibe3.observability.orchestra_log.append_orchestra_event")
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

        result = handle_supervisor_issue_identified(
            SupervisorIssueIdentified(
                issue_number=42,
                issue_title="Test governance issue",
                supervisor_file="supervisor.md",
            )
        )

        assert result is None
        mock_coordinator.dispatch_execution.assert_called_once()
