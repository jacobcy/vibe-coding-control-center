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


@pytest.mark.asyncio
async def test_force_recollect_queue_deduplication():
    """Test that fresh queue entries override waiting entries with same issue number."""
    config = OrchestraConfig()

    # Create mocks
    queue_persistence = MagicMock()
    queue_persistence.frozen_queue = None

    issue_loader = MagicMock()
    queue_selector = MagicMock()

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
        queue_selector=queue_selector,
    )

    # Set existing frozen queue with a waiting entry for issue 100
    from vibe3.models.orchestration import IssueState
    from vibe3.models.queue_entry import QueueEntry

    coordinator._frozen_queue = [
        QueueEntry(
            issue_number=100, collected_state="waiting_old", waiting_state="ready"
        ),
    ]

    # Mock issue collection to return fresh issue 100
    mock_collector = MagicMock()
    mock_issue = MagicMock()
    mock_issue.number = 100
    mock_collector.collect_open_issues.return_value = [mock_issue]

    coordinator._issue_collector_factory = lambda: mock_collector

    # Mock queue_selector to return the fresh issue only for READY state
    def queue_selector_side_effect(issues, state, *args, **kwargs):
        if state == IssueState.READY:
            return [mock_issue]
        return []

    queue_selector.side_effect = queue_selector_side_effect

    # Call force recollect
    await coordinator.force_recollect_queue()

    # Verify deduplication: fresh version used, waiting version dropped
    assert coordinator._frozen_queue is not None
    assert len(coordinator._frozen_queue) == 1
    assert coordinator._frozen_queue[0].issue_number == 100
    # Fresh entry has collected_state from the READY state
    assert coordinator._frozen_queue[0].collected_state == "ready"
    assert coordinator._frozen_queue[0].waiting_state is None


@pytest.mark.asyncio
async def test_force_recollect_queue_resets_dispatch_paused():
    """Test that force_recollect_queue resets _dispatch_paused to False."""
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

    # Set dispatch_paused to True before calling method
    coordinator._dispatch_paused = True

    # Mock issue collection
    mock_collector = MagicMock()
    mock_collector.collect_open_issues.return_value = []

    coordinator._issue_collector_factory = lambda: mock_collector

    # Call force recollect
    await coordinator.force_recollect_queue()

    # Verify dispatch_paused was reset to False
    assert coordinator._dispatch_paused is False


@pytest.mark.asyncio
async def test_force_recollect_queue_persistence_call():
    """Test that force_recollect_queue calls queue_persistence.persist()."""
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

    # Mock issue collection
    mock_collector = MagicMock()
    mock_collector.collect_open_issues.return_value = []

    coordinator._issue_collector_factory = lambda: mock_collector

    # Call force recollect
    await coordinator.force_recollect_queue()

    # Verify persist was called
    queue_persistence.persist.assert_called_once()
