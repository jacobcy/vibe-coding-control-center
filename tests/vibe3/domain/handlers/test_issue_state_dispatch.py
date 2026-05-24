"""Tests for manager dispatch-intent handler."""

from unittest.mock import MagicMock, patch

from vibe3.domain.events.flow_lifecycle import ManagerDispatchIntent


class TestIssueStateDispatchHandler:
    """issue_state_dispatch handler dispatches manager role."""

    def test_human_resume_event_does_not_dispatch(
        self,
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

    @patch("vibe3.domain.handlers.issue_state_dispatch.build_dispatch_context")
    @patch("vibe3.domain.handlers.issue_state_dispatch.load_orchestra_config")
    def test_ready_state_dispatches_manager(
        self,
        mock_config_cls: MagicMock,
        mock_build_context: MagicMock,
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

        # Create mock context with all required services
        mock_ctx = MagicMock()
        mock_ctx.capacity.can_dispatch.return_value = True
        mock_ctx.registry = MagicMock()
        mock_ctx.coordinator.dispatch_execution.return_value = ExecutionLaunchResult(
            launched=True,
        )

        # Mock build_manager_request to return a valid request
        with patch(
            "vibe3.domain.handlers.issue_state_dispatch.build_manager_request",
            return_value=mock_request,
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

        mock_ctx.coordinator.dispatch_execution.assert_called_once()

    @patch("vibe3.domain.handlers.issue_state_dispatch.build_dispatch_context")
    @patch("vibe3.domain.handlers.issue_state_dispatch.load_orchestra_config")
    def test_handoff_state_dispatches_manager(
        self,
        mock_config_cls: MagicMock,
        mock_build_context: MagicMock,
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

        # Create mock context with all required services
        mock_ctx = MagicMock()
        mock_ctx.capacity.can_dispatch.return_value = True
        mock_ctx.registry = MagicMock()
        mock_ctx.coordinator.dispatch_execution.return_value = ExecutionLaunchResult(
            launched=True,
        )

        # Mock build_manager_request to return a valid request
        with patch(
            "vibe3.domain.handlers.issue_state_dispatch.build_manager_request",
            return_value=mock_request,
        ):
            handle_manager_dispatch_intent(
                ManagerDispatchIntent(
                    issue_number=42,
                    branch="task/issue-42",
                    trigger_state="handoff",
                    issue_title="Test Issue",
                ),
                dispatch_context=mock_ctx,
            )

        mock_ctx.coordinator.dispatch_execution.assert_called_once()

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
    @patch("vibe3.domain.handlers.issue_state_dispatch.load_orchestra_config")
    def test_issue_fetch_failure_blocks_issue(
        self,
        mock_config_cls: MagicMock,
        mock_block_issue: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.issue_state_dispatch import (
            handle_manager_dispatch_intent,
        )

        mock_config = MagicMock()
        mock_config.max_concurrent_flows = 3
        mock_config_cls.return_value = mock_config

        # Create mock context with GitHub client that returns None
        mock_ctx = MagicMock()
        mock_ctx.capacity.can_dispatch.return_value = True
        mock_ctx.github_client.view_issue.return_value = None

        handle_manager_dispatch_intent(
            ManagerDispatchIntent(
                issue_number=42,
                branch="task/issue-42",
                trigger_state="ready",
            ),
            dispatch_context=mock_ctx,
        )

        mock_block_issue.assert_called_once_with(
            issue_number=42,
            repo=None,
            reason="Failed to fetch issue details from GitHub for manager dispatch",
            actor="agent:manager",
        )

    @patch("vibe3.domain.handlers.issue_state_dispatch.block_manager_noop_issue")
    @patch("vibe3.domain.handlers.issue_state_dispatch.load_orchestra_config")
    def test_issue_parse_failure_blocks_issue(
        self,
        mock_config_cls: MagicMock,
        mock_block_issue: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.issue_state_dispatch import (
            handle_manager_dispatch_intent,
        )

        mock_config = MagicMock()
        mock_config.max_concurrent_flows = 3
        mock_config_cls.return_value = mock_config

        # Create mock context with GitHub client that returns invalid payload
        mock_ctx = MagicMock()
        mock_ctx.capacity.can_dispatch.return_value = True
        mock_ctx.github_client.view_issue.return_value = {"id": "invalid_payload"}

        handle_manager_dispatch_intent(
            ManagerDispatchIntent(
                issue_number=42,
                branch="task/issue-42",
                trigger_state="ready",
            ),
            dispatch_context=mock_ctx,
        )

        mock_block_issue.assert_called_once_with(
            issue_number=42,
            repo=None,
            reason=(
                "Failed to parse issue data from GitHub response "
                "for manager dispatch"
            ),
            actor="agent:manager",
        )

    @patch("vibe3.domain.handlers.issue_state_dispatch.block_manager_noop_issue")
    @patch("vibe3.domain.handlers.issue_state_dispatch.load_orchestra_config")
    def test_request_none_blocks_issue(
        self,
        mock_config_cls: MagicMock,
        mock_block_issue: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.issue_state_dispatch import (
            handle_manager_dispatch_intent,
        )

        mock_config = MagicMock()
        mock_config_cls.return_value = mock_config

        # Create mock context
        mock_ctx = MagicMock()
        mock_ctx.capacity.can_dispatch.return_value = True
        mock_ctx.registry = MagicMock()
        mock_ctx.coordinator = MagicMock()

        # Mock build_manager_request to return None
        with patch(
            "vibe3.domain.handlers.issue_state_dispatch.build_manager_request",
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
        mock_block_issue.assert_called_once_with(
            issue_number=42,
            repo=None,
            reason="Failed to prepare role execution request",
            actor="agent:manager",
        )

    @patch("vibe3.domain.handlers.issue_state_dispatch.load_orchestra_config")
    def test_capacity_full_defers_without_blocking(
        self,
        mock_config_cls: MagicMock,
    ) -> None:
        """Test that capacity full defers dispatch without blocking the issue."""
        from vibe3.domain.handlers.issue_state_dispatch import (
            handle_manager_dispatch_intent,
        )

        mock_config = MagicMock()
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
        from vibe3.domain.handlers.issue_state_dispatch import (
            handle_manager_dispatch_intent,
        )
        from vibe3.exceptions import CapacityDeferredError

        mock_config = MagicMock()
        mock_config_cls.return_value = mock_config

        # Create mock context with capacity allowing dispatch
        mock_ctx = MagicMock()
        mock_ctx.capacity.can_dispatch.return_value = True
        mock_ctx.registry = MagicMock()
        mock_ctx.coordinator = MagicMock()

        # Mock build_request to raise CapacityDeferredError (race condition case)
        with patch(
            "vibe3.domain.handlers.issue_state_dispatch.build_manager_request",
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
