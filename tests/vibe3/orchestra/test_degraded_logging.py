"""Test degraded mode logging in GlobalDispatchCoordinator."""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.observability.degraded_mode import (
    DegradedModeManager,
    DegradedModeReason,
)
from vibe3.orchestra.global_dispatch_coordinator import (
    GlobalDispatchCoordinator,
    QueueEntry,
)


@pytest.fixture(autouse=True)
def reset_degraded_manager():
    """Reset degraded mode manager before and after each test."""
    DegradedModeManager.reset()
    yield
    DegradedModeManager.reset()


@patch(
    "vibe3.domain.dispatch_coordinator.get_manager_usernames",
    return_value=["manager-bot"],
)
def test_dispatch_logs_degraded_mode(mock_get_manager_usernames):
    """Test that dispatch logs when degraded mode is entered during qualification."""
    # Setup mocks
    mock_github = MagicMock()
    mock_store = MagicMock()
    mock_flow_manager = MagicMock()
    mock_capacity = MagicMock()
    mock_config = MagicMock(spec=OrchestraConfig)

    # Configure mocks
    mock_capacity.get_capacity_status.return_value = {"remaining": 1}
    mock_config.repo = "test/repo"
    mock_config.max_concurrent_flows = 1
    mock_config.max_retry_budget = 3
    mock_config.manager_usernames = ["manager-bot"]
    # Mock supervisor_handoff with issue_label
    mock_supervisor_handoff = MagicMock()
    mock_supervisor_handoff.issue_label = "supervisor"
    mock_config.supervisor_handoff = mock_supervisor_handoff

    # Create BLOCKED issue
    blocked_issue = IssueInfo(
        number=123,
        title="Test blocked issue",
        state=IssueState.BLOCKED,
        labels=["state/blocked"],
        assignees=["manager-bot"],
    )

    # Setup frozen queue with blocked issue
    frozen_queue = [
        QueueEntry(
            issue_number=123,
            collected_state="blocked",
            waiting_state=None,
        )
    ]

    # Mock qualify_gate to enter degraded mode
    def mock_qualify(issue):
        # Enter degraded mode during qualification
        manager = DegradedModeManager()
        manager.enter_degraded_mode(DegradedModeReason.GITHUB_API_TIMEOUT)
        return IssueState.READY  # Return a valid state

    with patch("vibe3.domain.dispatch_coordinator.load_issue") as mock_load_issue:
        with patch(
            "vibe3.domain.dispatch_coordinator.get_flow_context"
        ) as mock_flow_context:
            with patch("vibe3.domain.dispatch_coordinator.publish"):
                # Configure mock_store methods
                mock_store.load_frozen_queue.return_value = []
                mock_store.save_frozen_queue = MagicMock()
                mock_store.clear_frozen_queue = MagicMock()
                mock_store.remove_from_frozen_queue = MagicMock()

                mock_load_issue.return_value = blocked_issue
                mock_flow_context.return_value = ("task/issue-123", None)

                # Create coordinator
                coordinator = GlobalDispatchCoordinator(
                    config=mock_config,
                    capacity=mock_capacity,
                    github=mock_github,
                    store=mock_store,
                    flow_manager=mock_flow_manager,
                )

                # Set frozen queue
                coordinator._frozen_queue = frozen_queue

                # Mock qualify_gate
                coordinator._qualify_gate.qualify_blocked_issue = mock_qualify

                # Mock health check to pass
                coordinator._health_check_service.check_issue_health = (
                    lambda issue: True
                )

                # Run coordination with log capture
                import asyncio

                with patch("vibe3.domain.dispatch_coordinator.logger") as mock_logger:
                    asyncio.run(coordinator.coordinate(tick_id=1))

                    # Verify degraded mode warning was logged
                    degraded_calls = [
                        call
                        for call in mock_logger.bind.call_args_list
                        if "degraded_mode" in str(call)
                    ]

                    # Should have at least one call with degraded_mode=True
                    assert len(degraded_calls) > 0

                    # Verify the degraded mode warning was emitted
                    warning_calls = [
                        call
                        for call in mock_logger.bind.return_value.warning.call_args_list
                    ]
                    assert len(warning_calls) > 0

                    # Check that the log contains issue number
                    any_call_has_issue_123 = any(
                        "123" in str(call) for call in warning_calls
                    )
                    assert any_call_has_issue_123


@patch(
    "vibe3.domain.dispatch_coordinator.get_manager_usernames",
    return_value=["manager-bot"],
)
def test_dispatch_no_log_when_not_degraded(mock_get_manager_usernames):
    """Test that dispatch does not log degraded mode when not entered."""
    # Setup mocks
    mock_github = MagicMock()
    mock_store = MagicMock()
    mock_flow_manager = MagicMock()
    mock_capacity = MagicMock()
    mock_config = MagicMock(spec=OrchestraConfig)

    # Configure mocks
    mock_capacity.get_capacity_status.return_value = {"remaining": 1}
    mock_config.repo = "test/repo"
    mock_config.max_concurrent_flows = 1
    mock_config.max_retry_budget = 3
    mock_config.manager_usernames = ["manager-bot"]
    # Mock supervisor_handoff with issue_label
    mock_supervisor_handoff = MagicMock()
    mock_supervisor_handoff.issue_label = "supervisor"
    mock_config.supervisor_handoff = mock_supervisor_handoff

    # Create BLOCKED issue
    blocked_issue = IssueInfo(
        number=456,
        title="Test blocked issue",
        state=IssueState.BLOCKED,
        labels=["state/blocked"],
        assignees=["manager-bot"],
    )

    # Setup frozen queue with blocked issue
    frozen_queue = [
        QueueEntry(
            issue_number=456,
            collected_state="blocked",
            waiting_state=None,
        )
    ]

    # Mock qualify_gate to NOT enter degraded mode
    def mock_qualify(issue):
        # Do NOT enter degraded mode
        return IssueState.READY

    with patch("vibe3.domain.dispatch_coordinator.load_issue") as mock_load_issue:
        with patch(
            "vibe3.domain.dispatch_coordinator.get_flow_context"
        ) as mock_flow_context:
            with patch("vibe3.domain.dispatch_coordinator.publish"):
                # Configure mock_store methods
                mock_store.load_frozen_queue.return_value = []
                mock_store.save_frozen_queue = MagicMock()
                mock_store.clear_frozen_queue = MagicMock()
                mock_store.remove_from_frozen_queue = MagicMock()

                mock_load_issue.return_value = blocked_issue
                mock_flow_context.return_value = ("task/issue-456", None)

                # Create coordinator
                coordinator = GlobalDispatchCoordinator(
                    config=mock_config,
                    capacity=mock_capacity,
                    github=mock_github,
                    store=mock_store,
                    flow_manager=mock_flow_manager,
                )

                # Set frozen queue
                coordinator._frozen_queue = frozen_queue

                # Mock qualify_gate
                coordinator._qualify_gate.qualify_blocked_issue = mock_qualify

                # Mock health check to pass
                coordinator._health_check_service.check_issue_health = (
                    lambda issue: True
                )

                # Run coordination with log capture
                import asyncio

                with patch("vibe3.domain.dispatch_coordinator.logger") as mock_logger:
                    asyncio.run(coordinator.coordinate(tick_id=1))

                    # Verify NO degraded mode warning was logged
                    degraded_calls = [
                        call
                        for call in mock_logger.bind.call_args_list
                        if "degraded_mode" in str(call)
                    ]

                    # Should have NO calls with degraded_mode=True
                    assert len(degraded_calls) == 0
