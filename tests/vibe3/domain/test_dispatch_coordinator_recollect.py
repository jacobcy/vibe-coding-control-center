"""Test queue recollection functionality in GlobalDispatchCoordinator."""

from unittest.mock import MagicMock

import pytest

from vibe3.domain.dispatch_coordinator import GlobalDispatchCoordinator
from vibe3.models.orchestra_config import OrchestraConfig


@pytest.fixture
def mock_services():
    """Create mock services for GlobalDispatchCoordinator."""
    return {
        "capacity": MagicMock(),
        "github": MagicMock(),
        "store": MagicMock(),
        "flow_manager": MagicMock(),
        "health_check_service": MagicMock(),
        "queue_persistence": MagicMock(),
        "issue_loader": MagicMock(),
        "flow_context_resolver": MagicMock(),
        "queue_selector": MagicMock(),
    }


@pytest.mark.asyncio
async def test_force_recollect_queue_method_exists():
    """Test that force_recollect_queue() method exists."""
    config = OrchestraConfig()
    mock_services_dict = {
        "config": config,
        "capacity": MagicMock(),
        "github": MagicMock(),
        "store": MagicMock(),
        "flow_manager": MagicMock(),
        "health_check_service": MagicMock(),
        "queue_persistence": MagicMock(),
        "issue_loader": MagicMock(),
        "flow_context_resolver": MagicMock(),
        "queue_selector": MagicMock(),
    }

    coordinator = GlobalDispatchCoordinator(**mock_services_dict)

    assert hasattr(coordinator, "force_recollect_queue")
    assert callable(coordinator.force_recollect_queue)


@pytest.mark.asyncio
async def test_force_recollect_queue_clears_and_rebuilds():
    """Test that force_recollect_queue() clears queue and rebuilds with fresh data."""
    config = OrchestraConfig()

    # Create mocks
    queue_persistence = MagicMock()
    queue_persistence.frozen_queue = None

    issue_loader = MagicMock()

    coordinator = GlobalDispatchCoordinator(
        config=config,
        capacity=MagicMock(),
        github=MagicMock(),
        store=MagicMock(),
        flow_manager=MagicMock(),
        health_check_service=MagicMock(),
        queue_persistence=queue_persistence,
        issue_loader=issue_loader,
        flow_context_resolver=MagicMock(),
        queue_selector=MagicMock(),
    )

    # Set existing frozen queue with a waiting entry (should be preserved)
    from vibe3.models.queue_entry import QueueEntry

    coordinator._frozen_queue = [
        QueueEntry(issue_number=100, collected_state="ready", waiting_state="ready"),
        QueueEntry(issue_number=101, collected_state="ready", waiting_state=None),
    ]

    # Mock issue collection to return fresh issues
    mock_collector = MagicMock()
    mock_collector.collect_open_issues.return_value = []

    coordinator._issue_collector_factory = lambda: mock_collector

    # Call force recollect
    await coordinator.force_recollect_queue()

    # Verify queue was rebuilt (waiting entry preserved, non-waiting cleared)
    assert coordinator._frozen_queue is not None
    assert len(coordinator._frozen_queue) == 1  # Only waiting entry preserved
    assert coordinator._frozen_queue[0].issue_number == 100
