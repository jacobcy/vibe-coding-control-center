"""Tests for GlobalDispatchCoordinator HANDOFF qualify gate wiring.

Verifies that HANDOFF issues go through qualify_handoff_issue at dispatch
time, matching the pattern used for BLOCKED issues.
"""

from unittest.mock import Mock, patch

import pytest

from vibe3.domain.dispatch_coordinator import GlobalDispatchCoordinator
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState


@pytest.fixture
def mock_config():
    config = OrchestraConfig(repo="test/repo")
    return config


@pytest.fixture
def mock_capacity():
    capacity = Mock()
    capacity.get_capacity_status.return_value = {"remaining": 5}
    capacity.record_dispatch.return_value = None
    return capacity


@pytest.fixture
def mock_github():
    return Mock()


@pytest.fixture
def mock_store():
    store = Mock()
    store.db_path = ":memory:"
    store.get_flow_state = Mock(return_value=None)
    return store


@pytest.fixture
def mock_flow_manager():
    fm = Mock()
    fm.git = Mock()
    return fm


@pytest.fixture
def coordinator(mock_config, mock_capacity, mock_github, mock_store, mock_flow_manager):
    """Create coordinator with minimal mocked dependencies."""
    with (
        patch("vibe3.domain.dispatch_coordinator.CheckService"),
        patch("vibe3.domain.dispatch_coordinator.FlowService"),
        patch("vibe3.domain.dispatch_coordinator.DispatchHealthCheckService"),
        patch("vibe3.domain.dispatch_coordinator.IssueCollectionService"),
        patch("vibe3.domain.dispatch_coordinator.QueuePersistenceService"),
    ):
        coord = GlobalDispatchCoordinator(
            config=mock_config,
            capacity=mock_capacity,
            github=mock_github,
            store=mock_store,
            flow_manager=mock_flow_manager,
        )
    return coord


class TestDispatchCoordinatorHandoffQualify:
    """Tests for HANDOFF qualify gate wiring in _dispatch_intents."""

    def test_handoff_issue_with_verdict_removed_from_queue(self, coordinator):
        """HANDOFF issue where qualify_handoff_issue returns None is removed.

        This is the core regression: after reviewer sets verdict PASS,
        the next heartbeat tick must NOT re-dispatch manager.
        """
        from vibe3.orchestra.queue_operations import QueueEntry

        handoff_issue = IssueInfo(
            number=1678,
            title="Has verdict PASS",
            state=IssueState.HANDOFF,
            labels=["state/handoff"],
            assignees=["manager-bot"],
        )

        coordinator._frozen_queue = [
            QueueEntry(issue_number=1678, collected_state="handoff")
        ]
        coordinator._load_issue = Mock(return_value=handoff_issue)
        coordinator._qualify_gate.qualify_handoff_issue = Mock(return_value=None)

        with (
            patch(
                "vibe3.domain.dispatch_coordinator.should_skip_from_queue",
                return_value=False,
            ),
            patch("vibe3.domain.dispatch_coordinator.append_orchestra_event"),
        ):
            result = coordinator._dispatch_loop(tick_id=9)

        assert result == 0
        assert len(coordinator._frozen_queue) == 0
        coordinator._qualify_gate.qualify_handoff_issue.assert_called_once_with(
            handoff_issue
        )

    def test_handoff_issue_without_verdict_dispatches(self, coordinator):
        """HANDOFF issue where qualify_handoff_issue returns HANDOFF is dispatched."""
        from vibe3.orchestra.queue_operations import QueueEntry

        handoff_issue = IssueInfo(
            number=1679,
            title="No verdict, needs manager",
            state=IssueState.HANDOFF,
            labels=["state/handoff"],
            assignees=["manager-bot"],
        )

        coordinator._frozen_queue = [
            QueueEntry(issue_number=1679, collected_state="handoff")
        ]
        coordinator._load_issue = Mock(return_value=handoff_issue)
        coordinator._qualify_gate.qualify_handoff_issue = Mock(
            return_value=IssueState.HANDOFF
        )
        coordinator._health_check_service = Mock()
        coordinator._health_check_service.check_issue_health.return_value = True
        coordinator._emit_dispatch_intent = Mock(return_value=None)

        with (
            patch(
                "vibe3.domain.dispatch_coordinator.should_skip_from_queue",
                return_value=False,
            ),
            patch("vibe3.domain.dispatch_coordinator.append_orchestra_event"),
        ):
            coordinator._dispatch_loop(tick_id=10)

        coordinator._qualify_gate.qualify_handoff_issue.assert_called_once_with(
            handoff_issue
        )
