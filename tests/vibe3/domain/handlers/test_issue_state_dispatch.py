"""Tests for manager dispatch-intent handler."""

from unittest.mock import MagicMock, patch

from vibe3.domain.events.flow_lifecycle import ManagerDispatchIntent


class TestIssueStateDispatchHandler:
    """issue_state_dispatch handler dispatches manager role."""

    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.issue_state_dispatch.build_manager_request")
    @patch("vibe3.domain.handlers.issue_state_dispatch.load_orchestra_config")
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

        mock_config_cls.assert_not_called()
        mock_build_request.assert_not_called()
        mock_coordinator_cls.assert_not_called()

    @patch("vibe3.execution.capacity_service.CapacityService")
    @patch("vibe3.environment.session_registry.SessionRegistryService")
    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.issue_state_dispatch.load_orchestra_config")
    @patch("vibe3.domain.handlers.issue_state_dispatch.build_manager_request")
    def test_ready_state_dispatches_manager(
        self,
        mock_build_request: MagicMock,
        mock_config_cls: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_registry_cls: MagicMock,
        mock_capacity_cls: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.issue_state_dispatch import (
            handle_manager_dispatch_intent,
        )
        from vibe3.execution.contracts import ExecutionLaunchResult

        mock_config = MagicMock()
        mock_config.max_concurrent_flows = 3
        mock_config_cls.return_value = mock_config

        mock_request = MagicMock()
        mock_request.role = "manager"
        mock_build_request.return_value = mock_request

        mock_coordinator = MagicMock()
        mock_coordinator.dispatch_execution.return_value = ExecutionLaunchResult(
            launched=True,
        )
        mock_coordinator_cls.return_value = mock_coordinator

        # Mock capacity service to allow dispatch
        mock_capacity = MagicMock()
        mock_capacity.can_dispatch.return_value = True
        mock_capacity_cls.return_value = mock_capacity

        handle_manager_dispatch_intent(
            ManagerDispatchIntent(
                issue_number=42,
                branch="task/issue-42",
                trigger_state="ready",
                issue_title="Test Issue",
            )
        )

        mock_build_request.assert_called_once()

    @patch("vibe3.execution.capacity_service.CapacityService")
    @patch("vibe3.environment.session_registry.SessionRegistryService")
    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.issue_state_dispatch.load_orchestra_config")
    @patch("vibe3.domain.handlers.issue_state_dispatch.build_manager_request")
    def test_handoff_state_dispatches_manager(
        self,
        mock_build_request: MagicMock,
        mock_config_cls: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_registry_cls: MagicMock,
        mock_capacity_cls: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.issue_state_dispatch import (
            handle_manager_dispatch_intent,
        )
        from vibe3.execution.contracts import ExecutionLaunchResult

        mock_config = MagicMock()
        mock_config.max_concurrent_flows = 3
        mock_config_cls.return_value = mock_config

        mock_request = MagicMock()
        mock_request.role = "manager"
        mock_build_request.return_value = mock_request

        mock_coordinator = MagicMock()
        mock_coordinator.dispatch_execution.return_value = ExecutionLaunchResult(
            launched=True,
        )
        mock_coordinator_cls.return_value = mock_coordinator

        # Mock capacity service to allow dispatch
        mock_capacity = MagicMock()
        mock_capacity.can_dispatch.return_value = True
        mock_capacity_cls.return_value = mock_capacity

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

    @patch("vibe3.execution.capacity_service.CapacityService")
    @patch("vibe3.domain.handlers.issue_state_dispatch.block_manager_noop_issue")
    @patch("vibe3.clients.github_client.GitHubClient")
    @patch("vibe3.environment.session_registry.SessionRegistryService")
    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.issue_state_dispatch.load_orchestra_config")
    @patch("vibe3.domain.handlers.issue_state_dispatch.build_manager_request")
    def test_issue_fetch_failure_blocks_issue(
        self,
        mock_build_request: MagicMock,
        mock_config_cls: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_registry_cls: MagicMock,
        mock_github_client_cls: MagicMock,
        mock_block_issue: MagicMock,
        mock_capacity_cls: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.issue_state_dispatch import (
            handle_manager_dispatch_intent,
        )

        mock_config = MagicMock()
        mock_config.max_concurrent_flows = 3
        mock_config_cls.return_value = mock_config
        mock_github_client = MagicMock()
        mock_github_client.view_issue.return_value = None
        mock_github_client_cls.return_value = mock_github_client

        # Mock capacity service to allow dispatch
        mock_capacity = MagicMock()
        mock_capacity.can_dispatch.return_value = True
        mock_capacity_cls.return_value = mock_capacity

        handle_manager_dispatch_intent(
            ManagerDispatchIntent(
                issue_number=42,
                branch="task/issue-42",
                trigger_state="ready",
            )
        )

        mock_build_request.assert_not_called()
        mock_coordinator_cls.return_value.dispatch_execution.assert_not_called()
        mock_block_issue.assert_called_once_with(
            issue_number=42,
            repo=None,
            reason="Failed to fetch issue details from GitHub for manager dispatch",
            actor="agent:manager",
        )

    @patch("vibe3.execution.capacity_service.CapacityService")
    @patch("vibe3.domain.handlers.issue_state_dispatch.block_manager_noop_issue")
    @patch("vibe3.clients.github_client.GitHubClient")
    @patch("vibe3.environment.session_registry.SessionRegistryService")
    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.issue_state_dispatch.load_orchestra_config")
    @patch("vibe3.domain.handlers.issue_state_dispatch.build_manager_request")
    def test_issue_parse_failure_blocks_issue(
        self,
        mock_build_request: MagicMock,
        mock_config_cls: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_registry_cls: MagicMock,
        mock_github_client_cls: MagicMock,
        mock_block_issue: MagicMock,
        mock_capacity_cls: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.issue_state_dispatch import (
            handle_manager_dispatch_intent,
        )

        mock_config = MagicMock()
        mock_config.max_concurrent_flows = 3
        mock_config_cls.return_value = mock_config
        mock_github_client = MagicMock()
        mock_github_client.view_issue.return_value = {"id": "invalid_payload"}
        mock_github_client_cls.return_value = mock_github_client

        # Mock capacity service to allow dispatch
        mock_capacity = MagicMock()
        mock_capacity.can_dispatch.return_value = True
        mock_capacity_cls.return_value = mock_capacity

        handle_manager_dispatch_intent(
            ManagerDispatchIntent(
                issue_number=42,
                branch="task/issue-42",
                trigger_state="ready",
            )
        )

        mock_build_request.assert_not_called()
        mock_coordinator_cls.return_value.dispatch_execution.assert_not_called()
        mock_block_issue.assert_called_once_with(
            issue_number=42,
            repo=None,
            reason=(
                "Failed to parse issue data from GitHub response "
                "for manager dispatch"
            ),
            actor="agent:manager",
        )

    @patch("vibe3.execution.capacity_service.CapacityService")
    @patch("vibe3.domain.handlers.issue_state_dispatch.block_manager_noop_issue")
    @patch("vibe3.environment.session_registry.SessionRegistryService")
    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.issue_state_dispatch.load_orchestra_config")
    @patch("vibe3.domain.handlers.issue_state_dispatch.build_manager_request")
    def test_request_none_blocks_issue(
        self,
        mock_build_request: MagicMock,
        mock_config_cls: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_registry_cls: MagicMock,
        mock_block_issue: MagicMock,
        mock_capacity_cls: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.issue_state_dispatch import (
            handle_manager_dispatch_intent,
        )

        mock_config = MagicMock()
        mock_config_cls.return_value = mock_config

        # Mock capacity service to allow dispatch
        mock_capacity = MagicMock()
        mock_capacity.can_dispatch.return_value = True
        mock_capacity_cls.return_value = mock_capacity

        mock_build_request.return_value = None

        mock_coordinator = MagicMock()
        mock_coordinator_cls.return_value = mock_coordinator

        # Provide issue_title to skip GitHub API call
        handle_manager_dispatch_intent(
            ManagerDispatchIntent(
                issue_number=42,
                branch="task/issue-42",
                trigger_state="ready",
                issue_title="Test Issue",
            )
        )

        mock_coordinator.dispatch_execution.assert_not_called()
        mock_block_issue.assert_called_once_with(
            issue_number=42,
            repo=None,
            reason="Failed to prepare role execution request",
            actor="agent:manager",
        )

    @patch("vibe3.execution.capacity_service.CapacityService")
    @patch("vibe3.domain.handlers.issue_state_dispatch.block_manager_noop_issue")
    @patch("vibe3.environment.session_registry.SessionRegistryService")
    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.issue_state_dispatch.load_orchestra_config")
    @patch("vibe3.domain.handlers.issue_state_dispatch.build_manager_request")
    def test_capacity_full_defers_without_blocking(
        self,
        mock_build_request: MagicMock,
        mock_config_cls: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_registry_cls: MagicMock,
        mock_block_issue: MagicMock,
        mock_capacity_cls: MagicMock,
    ) -> None:
        """Test that capacity full defers dispatch without blocking the issue."""
        from vibe3.domain.handlers.issue_state_dispatch import (
            handle_manager_dispatch_intent,
        )

        mock_config = MagicMock()
        mock_config_cls.return_value = mock_config

        # Mock capacity service to deny dispatch
        mock_capacity = MagicMock()
        mock_capacity.can_dispatch.return_value = False
        mock_capacity_cls.return_value = mock_capacity

        mock_build_request.return_value = None

        mock_coordinator = MagicMock()
        mock_coordinator_cls.return_value = mock_coordinator

        # Provide issue_title to skip GitHub API call
        handle_manager_dispatch_intent(
            ManagerDispatchIntent(
                issue_number=42,
                branch="task/issue-42",
                trigger_state="ready",
                issue_title="Test Issue",
            )
        )

        # Capacity full should NOT call build_request or block_issue
        # It should just return early (defer)
        mock_build_request.assert_not_called()
        mock_coordinator.dispatch_execution.assert_not_called()
        mock_block_issue.assert_not_called()

    @patch("vibe3.execution.capacity_service.CapacityService")
    @patch("vibe3.domain.handlers.issue_state_dispatch.block_manager_noop_issue")
    @patch("vibe3.environment.session_registry.SessionRegistryService")
    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.issue_state_dispatch.load_orchestra_config")
    @patch("vibe3.domain.handlers.issue_state_dispatch.build_manager_request")
    def test_capacity_deferred_error_defers_without_blocking(
        self,
        mock_build_request: MagicMock,
        mock_config_cls: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_registry_cls: MagicMock,
        mock_block_issue: MagicMock,
        mock_capacity_cls: MagicMock,
    ) -> None:
        """Test CapacityDeferredError from build_request defers without blocking."""
        from vibe3.domain.handlers.issue_state_dispatch import (
            handle_manager_dispatch_intent,
        )
        from vibe3.exceptions import CapacityDeferredError

        mock_config = MagicMock()
        mock_config_cls.return_value = mock_config

        # Mock capacity service to allow dispatch initially
        mock_capacity = MagicMock()
        mock_capacity.can_dispatch.return_value = True
        mock_capacity_cls.return_value = mock_capacity

        # Mock build_request to raise CapacityDeferredError (race condition case)
        mock_build_request.side_effect = CapacityDeferredError(
            "Manager capacity reached (3/3). Deferred flow creation."
        )

        mock_coordinator = MagicMock()
        mock_coordinator_cls.return_value = mock_coordinator

        # Provide issue_title to skip GitHub API call
        handle_manager_dispatch_intent(
            ManagerDispatchIntent(
                issue_number=42,
                branch="task/issue-42",
                trigger_state="ready",
                issue_title="Test Issue",
            )
        )

        # CapacityDeferredError should NOT block the issue
        # It should just return early (defer)
        mock_coordinator.dispatch_execution.assert_not_called()
        mock_block_issue.assert_not_called()
