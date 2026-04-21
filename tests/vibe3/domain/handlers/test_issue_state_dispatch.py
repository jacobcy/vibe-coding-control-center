"""Tests for manager dispatch-intent handler."""

from unittest.mock import MagicMock, patch

from vibe3.domain.events.flow_lifecycle import ManagerDispatchIntent


class TestIssueStateDispatchHandler:
    """issue_state_dispatch handler dispatches manager role."""

    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.issue_state_dispatch.build_manager_request")
    @patch("vibe3.domain.handlers.issue_state_dispatch.OrchestraConfig")
    def test_human_resume_event_does_not_dispatch(
        self,
        mock_config_cls: MagicMock,
        mock_build_request: MagicMock,
        mock_coordinator_cls: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.issue_state_dispatch import (
            handle_manager_dispatch_intent,
        )

        handle_manager_dispatch_intent(
            ManagerDispatchIntent(
                issue_number=42,
                branch="task/issue-42",
                trigger_state="ready",
                actor="human:resume",
            )
        )

        mock_config_cls.from_settings.assert_not_called()
        mock_build_request.assert_not_called()
        mock_coordinator_cls.assert_not_called()

    @patch("vibe3.environment.session_registry.SessionRegistryService")
    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.issue_state_dispatch.OrchestraConfig")
    @patch("vibe3.domain.handlers.issue_state_dispatch.build_manager_request")
    def test_ready_state_dispatches_manager(
        self,
        mock_build_request: MagicMock,
        mock_config_cls: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_registry_cls: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.issue_state_dispatch import (
            handle_manager_dispatch_intent,
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

        handle_manager_dispatch_intent(
            ManagerDispatchIntent(
                issue_number=42,
                branch="task/issue-42",
                trigger_state="ready",
                issue_title="Test Issue",
            )
        )

        mock_build_request.assert_called_once()

    @patch("vibe3.environment.session_registry.SessionRegistryService")
    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.issue_state_dispatch.OrchestraConfig")
    @patch("vibe3.domain.handlers.issue_state_dispatch.build_manager_request")
    def test_handoff_state_dispatches_manager(
        self,
        mock_build_request: MagicMock,
        mock_config_cls: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_registry_cls: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.issue_state_dispatch import (
            handle_manager_dispatch_intent,
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

        handle_manager_dispatch_intent(
            ManagerDispatchIntent(
                issue_number=42,
                branch="task/issue-42",
                trigger_state="handoff",
                issue_title="Test Issue",
            )
        )

        mock_build_request.assert_called_once()

    def test_unknown_state_no_dispatch(self) -> None:
        from vibe3.domain.handlers.issue_state_dispatch import (
            handle_manager_dispatch_intent,
        )

        handle_manager_dispatch_intent(
            ManagerDispatchIntent(
                issue_number=42,
                branch="task/issue-42",
                trigger_state="claimed",
            )
        )

    @patch("vibe3.domain.handlers.issue_state_dispatch.block_manager_noop_issue")
    @patch("vibe3.environment.session_registry.SessionRegistryService")
    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.issue_state_dispatch.OrchestraConfig")
    @patch("vibe3.domain.handlers.issue_state_dispatch.build_manager_request")
    def test_request_none_blocks_issue(
        self,
        mock_build_request: MagicMock,
        mock_config_cls: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_registry_cls: MagicMock,
        mock_block_issue: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.issue_state_dispatch import (
            handle_manager_dispatch_intent,
        )

        mock_config = MagicMock()
        mock_config_cls.from_settings.return_value = mock_config

        mock_build_request.return_value = None

        mock_coordinator = MagicMock()
        mock_coordinator_cls.return_value = mock_coordinator

        handle_manager_dispatch_intent(
            ManagerDispatchIntent(
                issue_number=42,
                branch="task/issue-42",
                trigger_state="ready",
            )
        )

        mock_coordinator.dispatch_execution.assert_not_called()
        mock_block_issue.assert_called_once_with(
            issue_number=42,
            repo=None,
            reason="Failed to prepare role execution request",
            actor="agent:manager",
        )
