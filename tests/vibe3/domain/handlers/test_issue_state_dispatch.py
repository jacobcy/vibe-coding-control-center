"""Tests for manager dispatch-intent handler.

Tests cover:
- Guard logic (only handle ready/handoff trigger states)
- Skip logic for human:resume actor
- Fast path: event carries issue_title, no GitHub fetch needed
- Slow path: event missing issue_title, falls back to view_issue
- Manager role dispatch via ExecutionCoordinator
"""

from unittest.mock import MagicMock, patch

from vibe3.domain.events.flow_lifecycle import ManagerDispatchIntent
from vibe3.domain.handlers.issue_state_dispatch import handle_manager_dispatch_intent
from vibe3.models.orchestration import IssueState


def _make_event(
    issue_number: int = 42,
    trigger_state: str = "ready",
    branch: str = "task/issue-42",
    issue_title: str | None = None,
    actor: str = "orchestra:dispatcher",
) -> ManagerDispatchIntent:
    """Create a sample ManagerDispatchIntent event."""
    return ManagerDispatchIntent(
        issue_number=issue_number,
        branch=branch,
        trigger_state=trigger_state,
        issue_title=issue_title,
        actor=actor,
    )


def _make_github_response(
    number: int = 42,
    title: str = "Test issue",
    state: str = "open",
) -> dict:
    """Create a sample GitHub API response."""
    return {
        "number": number,
        "title": title,
        "state": state,
        "body": "Test body",
        "labels": [{"name": "state/ready"}],
        "assignees": [],
        "milestone": None,
    }


class TestIssueStateDispatchHandler:
    """issue_state_dispatch handler dispatches manager role."""

    @patch("vibe3.domain.handlers.issue_state_dispatch.load_orchestra_config")
    def test_ignores_non_manager_trigger_state(
        self,
        mock_config_cls: MagicMock,
    ) -> None:
        """Handler should return early when trigger_state is not ready/handoff."""
        mock_config_cls.return_value = MagicMock()

        event = _make_event(trigger_state="in-progress")

        # Should not raise and should not create any services
        handle_manager_dispatch_intent(event)

        # No services should be created for non-trigger states
        mock_config_cls.assert_not_called()

    def test_skips_human_resume_actor(self) -> None:
        """Handler should skip dispatch for human:resume actor."""
        event = _make_event(actor="human:resume")

        # Should not raise and should not create any services
        handle_manager_dispatch_intent(event)

    @patch("vibe3.execution.capacity_service.CapacityService")
    @patch("vibe3.environment.session_registry.SessionRegistryService")
    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.issue_state_dispatch.load_orchestra_config")
    @patch("vibe3.roles.build_manager_request")
    def test_ready_state_dispatches_manager(
        self,
        mock_build_request: MagicMock,
        mock_config_cls: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_registry_cls: MagicMock,
        mock_capacity_cls: MagicMock,
    ) -> None:
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
    @patch("vibe3.roles.build_manager_request")
    def test_handoff_state_dispatches_manager(
        self,
        mock_build_request: MagicMock,
        mock_config_cls: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_registry_cls: MagicMock,
        mock_capacity_cls: MagicMock,
    ) -> None:
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

    @patch("vibe3.execution.capacity_service.CapacityService")
    @patch("vibe3.roles.build_manager_request")
    @patch("vibe3.domain.handlers.issue_state_dispatch.block_manager_noop_issue")
    @patch("vibe3.clients.github_client.GitHubClient")
    @patch("vibe3.domain.handlers.issue_state_dispatch.load_orchestra_config")
    def test_records_failed_on_github_none(
        self,
        mock_config_cls: MagicMock,
        mock_github_cls: MagicMock,
        mock_block_noop: MagicMock,
        mock_build_request: MagicMock,
        mock_capacity_cls: MagicMock,
    ) -> None:
        """Handler should skip dispatch when GitHub returns None (slow path)."""
        mock_config = MagicMock()
        mock_config.max_concurrent_flows = 3
        mock_config_cls.return_value = mock_config

        mock_github = MagicMock()
        mock_github.view_issue.return_value = None
        mock_github_cls.return_value = mock_github

        # Mock capacity service to allow dispatch
        mock_capacity = MagicMock()
        mock_capacity.can_dispatch.return_value = True
        mock_capacity_cls.return_value = mock_capacity

        # No issue_title triggers slow path
        event = _make_event(issue_title=None)
        handle_manager_dispatch_intent(event)

        # Should NOT dispatch
        mock_build_request.assert_not_called()
        mock_block_noop.assert_called_once()

    @patch("vibe3.execution.capacity_service.CapacityService")
    @patch("vibe3.roles.build_manager_request")
    @patch("vibe3.domain.handlers.issue_state_dispatch.block_manager_noop_issue")
    @patch("vibe3.clients.github_client.GitHubClient")
    @patch("vibe3.domain.handlers.issue_state_dispatch.load_orchestra_config")
    def test_records_failed_on_network_error(
        self,
        mock_config_cls: MagicMock,
        mock_github_cls: MagicMock,
        mock_block_noop: MagicMock,
        mock_build_request: MagicMock,
        mock_capacity_cls: MagicMock,
    ) -> None:
        """Handler should skip dispatch when GitHub returns network error."""
        mock_config = MagicMock()
        mock_config.max_concurrent_flows = 3
        mock_config_cls.return_value = mock_config

        mock_github = MagicMock()
        mock_github.view_issue.return_value = "network_error"
        mock_github_cls.return_value = mock_github

        # Mock capacity service to allow dispatch
        mock_capacity = MagicMock()
        mock_capacity.can_dispatch.return_value = True
        mock_capacity_cls.return_value = mock_capacity

        event = _make_event(issue_title=None)
        handle_manager_dispatch_intent(event)

        mock_build_request.assert_not_called()
        mock_block_noop.assert_called_once()

    @patch("vibe3.execution.capacity_service.CapacityService")
    @patch("vibe3.roles.build_manager_request")
    @patch("vibe3.domain.handlers.issue_state_dispatch.block_manager_noop_issue")
    @patch("vibe3.clients.github_client.GitHubClient")
    @patch("vibe3.domain.handlers.issue_state_dispatch.load_orchestra_config")
    def test_records_failed_on_invalid_issue_data(
        self,
        mock_config_cls: MagicMock,
        mock_github_cls: MagicMock,
        mock_block_noop: MagicMock,
        mock_build_request: MagicMock,
        mock_capacity_cls: MagicMock,
    ) -> None:
        """Handler should skip dispatch when from_github_payload returns None."""
        mock_config = MagicMock()
        mock_config.max_concurrent_flows = 3
        mock_config_cls.return_value = mock_config

        mock_github = MagicMock()
        mock_github.view_issue.return_value = _make_github_response()
        mock_github_cls.return_value = mock_github

        # Mock capacity service to allow dispatch
        mock_capacity = MagicMock()
        mock_capacity.can_dispatch.return_value = True
        mock_capacity_cls.return_value = mock_capacity

        event = _make_event(issue_title=None)

        with patch(
            "vibe3.models.orchestration.IssueInfo.from_github_payload",
            return_value=None,
        ):
            handle_manager_dispatch_intent(event)

        mock_build_request.assert_not_called()
        mock_block_noop.assert_called_once()

    @patch("vibe3.domain.handlers.issue_state_dispatch.block_manager_noop_issue")
    @patch("vibe3.domain.handlers.issue_state_dispatch.load_orchestra_config")
    def test_request_none_blocks_issue(
        self,
        mock_config_cls: MagicMock,
        mock_block_issue: MagicMock,
    ) -> None:
        mock_config = MagicMock()
        mock_config.max_concurrent_flows = 3
        mock_config_cls.return_value = mock_config

        # Create mock context
        mock_ctx = MagicMock()
        mock_ctx.capacity.can_dispatch.return_value = True
        mock_ctx.registry = MagicMock()
        mock_ctx.coordinator = MagicMock()

        # Mock build_manager_request to return None
        with patch(
            "vibe3.roles.build_manager_request",
            return_value=None,
        ):
            handle_manager_dispatch_intent(
                ManagerDispatchIntent(
                    issue_number=42,
                    branch="task/issue-42",
                    trigger_state="ready",
                    issue_title="Test Issue",
                ),
                dispatch_context=mock_ctx,
            )

        mock_ctx.coordinator.dispatch_execution.assert_not_called()
        mock_block_issue.assert_called_once()

    @patch("vibe3.domain.handlers.issue_state_dispatch.load_orchestra_config")
    def test_capacity_full_defers_without_blocking(
        self,
        mock_config_cls: MagicMock,
    ) -> None:
        """Test that capacity full defers dispatch without blocking the issue."""
        mock_config = MagicMock()
        mock_config.max_concurrent_flows = 3
        mock_config_cls.return_value = mock_config

        # Create mock context with capacity denying dispatch
        mock_ctx = MagicMock()
        mock_ctx.capacity.can_dispatch.return_value = False

        with patch(
            "vibe3.domain.handlers.issue_state_dispatch.block_manager_noop_issue"
        ) as mock_block_issue:
            handle_manager_dispatch_intent(
                ManagerDispatchIntent(
                    issue_number=42,
                    branch="task/issue-42",
                    trigger_state="ready",
                    issue_title="Test Issue",
                ),
                dispatch_context=mock_ctx,
            )

            # Capacity full should NOT call build_request or block_issue
            # It should just return early (defer)
            mock_block_issue.assert_not_called()

    @patch("vibe3.domain.handlers.issue_state_dispatch.load_orchestra_config")
    def test_capacity_deferred_error_defers_without_blocking(
        self,
        mock_config_cls: MagicMock,
    ) -> None:
        """Test CapacityDeferredError from build_request defers without blocking."""
        from vibe3.exceptions import CapacityDeferredError

        mock_config = MagicMock()
        mock_config.max_concurrent_flows = 3
        mock_config_cls.return_value = mock_config

        # Create mock context with capacity allowing dispatch
        mock_ctx = MagicMock()
        mock_ctx.capacity.can_dispatch.return_value = True
        mock_ctx.registry = MagicMock()
        mock_ctx.coordinator = MagicMock()

        # Mock build_request to raise CapacityDeferredError (race condition case)
        with patch(
            "vibe3.roles.build_manager_request",
            side_effect=CapacityDeferredError(
                "Manager capacity reached (3/3). Deferred flow creation."
            ),
        ):
            with patch(
                "vibe3.domain.handlers.issue_state_dispatch.block_manager_noop_issue"
            ) as mock_block_issue:
                handle_manager_dispatch_intent(
                    ManagerDispatchIntent(
                        issue_number=42,
                        branch="task/issue-42",
                        trigger_state="ready",
                        issue_title="Test Issue",
                    ),
                    dispatch_context=mock_ctx,
                )

                # CapacityDeferredError should NOT block the issue
                # It should just return early (defer)
                mock_ctx.coordinator.dispatch_execution.assert_not_called()
                mock_block_issue.assert_not_called()

    @patch("vibe3.domain.handlers.issue_state_dispatch.build_dispatch_context")
    @patch("vibe3.domain.handlers.issue_state_dispatch.load_orchestra_config")
    def test_default_path_uses_factory(
        self,
        mock_config_cls: MagicMock,
        mock_build_context: MagicMock,
    ) -> None:
        """Test that not passing dispatch_context triggers the factory path."""
        mock_config = MagicMock()
        mock_config.max_concurrent_flows = 3
        mock_config_cls.return_value = mock_config

        mock_request = MagicMock()
        mock_request.role = "manager"

        # Create mock context with all required services
        mock_ctx = MagicMock()
        mock_ctx.config = mock_config
        mock_ctx.capacity.can_dispatch.return_value = True
        mock_ctx.registry = MagicMock()
        mock_ctx.coordinator.dispatch_execution.return_value = MagicMock(
            launched=True, reason=None
        )

        # Mock build_dispatch_context to return our mock context
        mock_build_context.return_value = mock_ctx

        # Mock build_manager_request to return a valid request
        with patch(
            "vibe3.roles.build_manager_request",
            return_value=mock_request,
        ):
            handle_manager_dispatch_intent(
                ManagerDispatchIntent(
                    issue_number=42,
                    branch="task/issue-42",
                    trigger_state="ready",
                    issue_title="Test Issue",
                )
                # Note: NOT passing dispatch_context, so factory should be used
            )

        # Verify factory was called
        mock_build_context.assert_called_once()
        mock_ctx.coordinator.dispatch_execution.assert_called_once()


class TestManagerHandlerDispatch:
    """Test manager role service dispatch via fast path (issue_title present)."""

    @patch("vibe3.execution.capacity_service.CapacityService")
    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.roles.build_manager_request")
    @patch("vibe3.domain.handlers.issue_state_dispatch.load_orchestra_config")
    def test_dispatch_success(
        self,
        mock_config_cls: MagicMock,
        mock_build_request: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_capacity_cls: MagicMock,
    ) -> None:
        """Handler should dispatch manager with correct IssueInfo via fast path."""
        mock_config = MagicMock()
        mock_config.max_concurrent_flows = 3
        mock_config_cls.return_value = mock_config

        mock_request = MagicMock()
        mock_request.role = "manager"
        mock_build_request.return_value = mock_request

        mock_coordinator = MagicMock()
        mock_coordinator.dispatch_execution.return_value = MagicMock(
            launched=True, reason=None
        )
        mock_coordinator_cls.return_value = mock_coordinator

        # Mock capacity service to allow dispatch
        mock_capacity = MagicMock()
        mock_capacity.can_dispatch.return_value = True
        mock_capacity_cls.return_value = mock_capacity

        # Provide issue_title to use the fast path
        event = _make_event(issue_title="Test issue")

        handle_manager_dispatch_intent(event)

        # Verify build_manager_request was called
        mock_build_request.assert_called_once()
        call_args = mock_build_request.call_args
        dispatched_issue = call_args[0][1]
        assert dispatched_issue.number == 42
        assert dispatched_issue.title == "Test issue"
        assert dispatched_issue.state == IssueState.READY
