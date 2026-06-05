"""End-to-end integration tests for queue priority refresh flow."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.clients import SQLiteClient
from vibe3.clients.sqlite_schema import init_schema
from vibe3.domain.dispatch_coordinator import GlobalDispatchCoordinator
from vibe3.models import IssueInfo
from vibe3.models.orchestra_config import OrchestraConfig, QueueRecollectConfig
from vibe3.orchestra.queue_entry import QueueEntry
from vibe3.runtime.heartbeat import HeartbeatServer
from vibe3.runtime.service_protocol import ServiceBase


class _MockDispatchService(ServiceBase):
    """Mock dispatch service for testing."""

    is_dispatch_service = True

    def __init__(self) -> None:
        self._coordinator: GlobalDispatchCoordinator | None = None
        self.ticks: list[int] = []

    def set_coordinator(self, coordinator: GlobalDispatchCoordinator) -> None:
        """Set the coordinator reference."""
        self._coordinator = coordinator

    async def on_tick(self, tick_id: int = 0) -> None:
        """Record tick calls."""
        self.ticks.append(tick_id)


@pytest.fixture
def temp_store(tmp_path: Path) -> SQLiteClient:
    """Create a temporary SQLiteClient for testing."""
    import sqlite3

    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    conn.close()
    return SQLiteClient(db_path=str(db_path))


@pytest.mark.asyncio
async def test_priority_label_update_triggers_queue_reorder(
    temp_store: SQLiteClient,
    monkeypatch,
) -> None:
    """Test queue automatically refreshes and reorders after priority label update.

    Scenario:
    - Initial queue: [#100, #200] in random order
    - Fresh collection returns high priority #200 first
    - Verify: Queue reordered to [#200, #100]
    """
    # Setup config with queue recollection
    config = OrchestraConfig(
        repo="owner/repo",
        polling_interval=1,
        max_concurrent_flows=3,
        queue_recollect=QueueRecollectConfig(enabled=True, interval_ticks=10),
        manager_usernames=["manager-bot"],
    )
    config.supervisor_handoff.issue_label = "supervisor"

    # Create mocks
    github = MagicMock()
    capacity = MagicMock()
    capacity.get_capacity_status = MagicMock(
        return_value={
            "remaining": 10,
            "active_count": 0,
            "max_capacity": 10,
        }
    )
    capacity._backend = None

    flow_manager = MagicMock()
    health_check_service = MagicMock()
    queue_persistence = MagicMock()

    def mock_issue_loader(issue_number: int) -> IssueInfo | None:
        return None

    coordinator = GlobalDispatchCoordinator(
        config=config,
        capacity=capacity,
        github=github,
        store=temp_store,
        flow_manager=flow_manager,
        registry=None,
        health_check_service=health_check_service,
        queue_persistence=queue_persistence,
        issue_loader=mock_issue_loader,
        flow_context_resolver=lambda n: (f"task/issue-{n}", None),
        queue_selector=lambda issues, state, *args, **kwargs: [],
    )

    # Manually set up initial queue (low priority first)
    coordinator._frozen_queue = [
        QueueEntry(issue_number=100, collected_state="ready"),
        QueueEntry(issue_number=200, collected_state="ready"),
    ]

    # Mock fresh collection to return high priority #200 first
    async def mock_collect_frozen_queue() -> list[QueueEntry]:
        return [
            QueueEntry(issue_number=200, collected_state="ready"),
            QueueEntry(issue_number=100, collected_state="ready"),
        ]

    # Patch _collect_frozen_queue to return reordered queue
    with patch.object(
        coordinator,
        "_collect_frozen_queue",
        mock_collect_frozen_queue,
    ):
        # Trigger recollection
        await coordinator.force_recollect_queue()

        # Verify queue reordered with high priority first
        assert coordinator._frozen_queue is not None
        assert len(coordinator._frozen_queue) == 2
        final_numbers = [e.issue_number for e in coordinator._frozen_queue]
        assert final_numbers[0] == 200, "High priority issue should be first"
        assert final_numbers[1] == 100, "Low priority issue should be second"


@pytest.mark.asyncio
async def test_in_flight_entries_preserved_during_recollect(
    temp_store: SQLiteClient,
    monkeypatch,
) -> None:
    """Test queue recollection preserves in-flight entries.

    Scenario:
    - Queue has entry with waiting_state != None (in flight)
    - Fresh collection doesn't include this issue
    - Verify: Entry still in queue after recollection
    """
    # Setup config
    config = OrchestraConfig(
        repo="owner/repo",
        polling_interval=1,
        max_concurrent_flows=3,
        queue_recollect=QueueRecollectConfig(enabled=True, interval_ticks=10),
        manager_usernames=["manager-bot"],
    )
    config.supervisor_handoff.issue_label = "supervisor"

    # Create mocks
    github = MagicMock()
    capacity = MagicMock()
    capacity.get_capacity_status = MagicMock(
        return_value={
            "remaining": 10,
            "active_count": 0,
            "max_capacity": 10,
        }
    )
    capacity._backend = None

    flow_manager = MagicMock()
    health_check_service = MagicMock()
    queue_persistence = MagicMock()

    def mock_issue_loader(issue_number: int) -> IssueInfo | None:
        return None

    coordinator = GlobalDispatchCoordinator(
        config=config,
        capacity=capacity,
        github=github,
        store=temp_store,
        flow_manager=flow_manager,
        registry=None,
        health_check_service=health_check_service,
        queue_persistence=queue_persistence,
        issue_loader=mock_issue_loader,
        flow_context_resolver=lambda n: (f"task/issue-{n}", None),
        queue_selector=lambda issues, state, *args, **kwargs: [],
    )

    # Set up queue with in-flight entry
    in_flight_entry = QueueEntry(
        issue_number=100,
        collected_state="ready",
        waiting_state="ready",  # In flight
    )
    coordinator._frozen_queue = [
        in_flight_entry,
        QueueEntry(issue_number=200, collected_state="ready"),
    ]

    # Mock fresh collection that doesn't include #100
    async def mock_collect_frozen_queue() -> list[QueueEntry]:
        return [
            QueueEntry(issue_number=200, collected_state="ready"),
        ]

    with patch.object(
        coordinator,
        "_collect_frozen_queue",
        mock_collect_frozen_queue,
    ):
        # Trigger recollection
        await coordinator.force_recollect_queue()

        # Verify in-flight entry preserved
        assert coordinator._frozen_queue is not None
        numbers = [e.issue_number for e in coordinator._frozen_queue]
        assert 100 in numbers, "In-flight entry should be preserved"
        assert 200 in numbers, "Fresh entry should be added"

        # Verify waiting_state unchanged
        entry_100 = next(e for e in coordinator._frozen_queue if e.issue_number == 100)
        assert (
            entry_100.waiting_state == "ready"
        ), "Waiting state should not be modified"


@pytest.mark.asyncio
async def test_disabled_config_skips_recollect(
    temp_store: SQLiteClient,
    monkeypatch,
) -> None:
    """Test disabled configuration doesn't trigger queue recollection.

    Scenario:
    - queue_recollect.enabled = False
    - Run heartbeat to tick 10
    - Verify: force_recollect_queue() not called
    """
    # Setup config with recollection disabled
    config = OrchestraConfig(
        repo="owner/repo",
        polling_interval=1,
        max_concurrent_flows=3,
        queue_recollect=QueueRecollectConfig(enabled=False, interval_ticks=10),
        manager_usernames=["manager-bot"],
    )
    config.supervisor_handoff.issue_label = "supervisor"

    # Create minimal mocks
    github = MagicMock()
    capacity = MagicMock()
    capacity.get_capacity_status = MagicMock(
        return_value={
            "remaining": 10,
            "active_count": 0,
            "max_capacity": 10,
        }
    )
    capacity._backend = None

    flow_manager = MagicMock()
    health_check_service = MagicMock()
    queue_persistence = MagicMock()

    def mock_issue_loader(issue_number: int) -> IssueInfo | None:
        return None

    coordinator = GlobalDispatchCoordinator(
        config=config,
        capacity=capacity,
        github=github,
        store=temp_store,
        flow_manager=flow_manager,
        registry=None,
        health_check_service=health_check_service,
        queue_persistence=queue_persistence,
        issue_loader=mock_issue_loader,
        flow_context_resolver=lambda n: (f"task/issue-{n}", None),
        queue_selector=lambda issues, state, *args, **kwargs: [],
    )

    # Create heartbeat server
    server = HeartbeatServer(config)
    dispatch_service = _MockDispatchService()
    dispatch_service.set_coordinator(coordinator)
    server.register(dispatch_service)

    # Track if force_recollect_queue was called
    recollect_called = {"count": 0}

    async def mock_recollect() -> None:
        recollect_called["count"] += 1

    # Patch force_recollect_queue
    with patch.object(coordinator, "force_recollect_queue", mock_recollect):
        # Mock asyncio.sleep to control tick progression
        tick_count = {"count": 0}

        async def mock_sleep(seconds: float) -> None:
            tick_count["count"] += 1
            if tick_count["count"] >= 12:  # Run past tick 10
                server.stop()

        monkeypatch.setattr("asyncio.sleep", mock_sleep)

        # Run server
        server._running = True
        await server._tick_loop()

    # Verify force_recollect_queue was not called
    assert (
        recollect_called["count"] == 0
    ), "force_recollect_queue should not be called when disabled"
