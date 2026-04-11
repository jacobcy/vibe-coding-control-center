"""Tests for issue-state role dispatch handler."""

from unittest.mock import MagicMock, patch

from vibe3.domain.events.flow_lifecycle import IssueStateChanged


class TestIssueStateDispatchHandler:
    """issue_state_dispatch handler dispatches manager role."""

    # Dispatches on state/ready or state/handoff

    @patch("vibe3.environment.session_registry.SessionRegistryService")
    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.issue_state_dispatch.OrchestraConfig")
    @patch("vibe3.domain.handlers.issue_state_dispatch.build_issue_state_request")
    def test_ready_state_dispatches_manager(
        self,
        mock_build_request: MagicMock,
        mock_config_cls: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_registry_cls: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.issue_state_dispatch import (
            handle_issue_state_changed_for_roles,
        )
        from vibe3.execution.contracts import ExecutionLaunchResult

        mock_config = MagicMock()
        mock_config_cls.from_settings.return_value = mock_config

        mock_request = MagicMock()
        mock_request.role = "manager"
        mock_build_request.return_value = mock_request

        mock_coordinator = MagicMock()
        mock_coordinator.dispatch_execution.return_value = ExecutionLaunchResult(
            launched=True,
        )
        mock_coordinator_cls.return_value = mock_coordinator

        handle_issue_state_changed_for_roles(
            IssueStateChanged(
                issue_number=42,
                from_state=None,
                to_state="ready",
                issue_title="Test issue",
            )
        )

        mock_build_request.assert_called_once()

    @patch("vibe3.environment.session_registry.SessionRegistryService")
    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.issue_state_dispatch.OrchestraConfig")
    @patch("vibe3.domain.handlers.issue_state_dispatch.build_issue_state_request")
    def test_handoff_state_dispatches_manager(
        self,
        mock_build_request: MagicMock,
        mock_config_cls: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_registry_cls: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.issue_state_dispatch import (
            handle_issue_state_changed_for_roles,
        )
        from vibe3.execution.contracts import ExecutionLaunchResult

        mock_config = MagicMock()
        mock_config_cls.from_settings.return_value = mock_config

        mock_request = MagicMock()
        mock_request.role = "manager"
        mock_build_request.return_value = mock_request

        mock_coordinator = MagicMock()
        mock_coordinator.dispatch_execution.return_value = ExecutionLaunchResult(
            launched=True,
        )
        mock_coordinator_cls.return_value = mock_coordinator

        handle_issue_state_changed_for_roles(
            IssueStateChanged(
                issue_number=42,
                from_state="ready",
                to_state="handoff",
                issue_title="Test issue",
            )
        )

        mock_build_request.assert_called_once()

    def test_unknown_state_no_dispatch(self) -> None:
        from vibe3.domain.handlers.issue_state_dispatch import (
            handle_issue_state_changed_for_roles,
        )

        # "claimed" is not a supported manager state.
        # resolve_issue_state_role returns None, so no-op.
        # This should be a no-op, no exceptions
        handle_issue_state_changed_for_roles(
            IssueStateChanged(
                issue_number=42,
                from_state="ready",
                to_state="claimed",
                issue_title="Test issue",
            )
        )

    @patch("vibe3.environment.session_registry.SessionRegistryService")
    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.issue_state_dispatch.OrchestraConfig")
    @patch("vibe3.domain.handlers.issue_state_dispatch.build_issue_state_request")
    def test_request_none_logs_error(
        self,
        mock_build_request: MagicMock,
        mock_config_cls: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_registry_cls: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.issue_state_dispatch import (
            handle_issue_state_changed_for_roles,
        )

        mock_config = MagicMock()
        mock_config_cls.from_settings.return_value = mock_config

        mock_build_request.return_value = None

        mock_coordinator = MagicMock()
        mock_coordinator_cls.return_value = mock_coordinator

        handle_issue_state_changed_for_roles(
            IssueStateChanged(
                issue_number=42,
                from_state=None,
                to_state="ready",
                issue_title="Test issue",
            )
        )

        mock_coordinator.dispatch_execution.assert_not_called()
