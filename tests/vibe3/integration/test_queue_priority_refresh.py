"""End-to-end integration tests for queue priority refresh flow."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pytest import MonkeyPatch

from vibe3.clients import GitHubClient, SQLiteClient
from vibe3.clients.sqlite_schema import init_schema
from vibe3.domain.dispatch_coordinator import GlobalDispatchCoordinator
from vibe3.domain.protocols import FlowManagerProtocol
from vibe3.domain.qualify_gate import QualifyGateService
from vibe3.models import IssueInfo, IssueState
from vibe3.models.orchestra_config import OrchestraConfig, QueueRecollectConfig
from vibe3.orchestra.queue_entry import QueueEntry
from vibe3.runtime.heartbeat import HeartbeatServer
from vibe3.runtime.service_protocol import ServiceBase


class _MockDispatchService(ServiceBase):
    """Mock dispatch service for testing."""

    def __init__(self) -> None:
        self._coordinator: GlobalDispatchCoordinator | None = None
        self.ticks: list[int] = []

    @property
    def is_dispatch_service(self) -> bool:
        """Whether this service initiates automated flow/task actions."""
        return True

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
    monkeypatch: MonkeyPatch,
) -> None:
    """Test queue automatically refreshes and reorders after priority label update.

    Scenario:
    - Initial queue: [#100, #200] in random order
    - GitHub returns issues with priority labels (#200 has high priority)
    - queue_selector filters and prioritizes based on labels
    - Verify: Queue reordered to [#200, #100]
    """
    # Setup config with queue recollection
    config = OrchestraConfig(
        repo="owner/repo",
        polling_interval=1,
        max_concurrent_flows=3,
        queue_recollect=QueueRecollectConfig(enabled=True, interval_ticks=10),
        manager_usernames=("manager-bot",),
    )
    config.supervisor_handoff.issue_label = "supervisor"

    # Create mocks for external dependencies (GitHub API)
    github = MagicMock()

    # Mock GitHub to return issues with priority labels
    issue_100 = IssueInfo(
        number=100,
        title="Low priority issue",
        labels=["state/ready", "priority/low"],
        state=IssueState.READY,
        assignees=[],
    )
    issue_200 = IssueInfo(
        number=200,
        title="High priority issue",
        labels=["state/ready", "priority/high"],
        state=IssueState.READY,
        assignees=[],
    )

    # Mock issue collection to return issues in initial order
    github.list_issues = MagicMock(return_value=[issue_100, issue_200])

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
        # Return the corresponding issue info
        if issue_number == 100:
            return issue_100
        elif issue_number == 200:
            return issue_200
        return None

    def mock_flow_context_resolver(
        issue_number: int,
    ) -> tuple[str, dict[str, object] | None]:
        return (f"task/issue-{issue_number}", None)

    def priority_queue_selector(
        issues: list[IssueInfo],
        trigger_state: IssueState,
        config: OrchestraConfig,
        github: GitHubClient,
        store: SQLiteClient,
        flow_manager: FlowManagerProtocol,
        qualify_gate: QualifyGateService,
        supervisor_label: str,
    ) -> list[IssueInfo]:
        """Real queue selector that sorts by priority labels."""
        # Suppress unused parameter warnings
        _ = config, github, store, flow_manager, qualify_gate, supervisor_label

        # Filter by state (check both enum value and label format)
        ready_issues = [
            i
            for i in issues
            if (trigger_state in i.labels or trigger_state.to_label() in i.labels)
            and supervisor_label not in i.labels
        ]

        # Sort by priority (high > medium > low)
        def get_priority(issue: IssueInfo) -> int:
            if "priority/high" in issue.labels:
                return 3
            elif "priority/medium" in issue.labels:
                return 2
            elif "priority/low" in issue.labels:
                return 1
            return 0

        ready_issues.sort(key=get_priority, reverse=True)
        return ready_issues

    # Mock issue collector factory to return test issues
    mock_issue_collector = MagicMock()
    mock_issue_collector.collect_open_issues = MagicMock(
        return_value=[issue_100, issue_200]
    )

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
        flow_context_resolver=mock_flow_context_resolver,
        queue_selector=priority_queue_selector,
        issue_collector_factory=lambda: mock_issue_collector,
    )

    # Manually set up initial queue (low priority first)
    coordinator._frozen_queue = [
        QueueEntry(issue_number=100, collected_state="ready"),
        QueueEntry(issue_number=200, collected_state="ready"),
    ]

    # Trigger recollection (will call _collect_frozen_queue internally)
    # which uses queue_selector to prioritize based on labels
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
    monkeypatch: MonkeyPatch,
) -> None:
    """Test queue recollection preserves in-flight entries.

    Scenario:
    - Queue has entry with waiting_state != None (in flight)
    - Fresh collection doesn't include this issue (e.g., issue closed)
    - Verify: Entry still in queue after recollection with waiting_state preserved
    """
    # Setup config
    config = OrchestraConfig(
        repo="owner/repo",
        polling_interval=1,
        max_concurrent_flows=3,
        queue_recollect=QueueRecollectConfig(enabled=True, interval_ticks=10),
        manager_usernames=("manager-bot",),
    )
    config.supervisor_handoff.issue_label = "supervisor"

    # Create mocks
    github = MagicMock()

    # Mock GitHub to only return issue #200 (issue #100 is "closed")
    issue_200 = IssueInfo(
        number=200,
        title="Available issue",
        labels=["state/ready"],
        state=IssueState.READY,
        assignees=[],
    )

    github.list_issues = MagicMock(return_value=[issue_200])

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
        if issue_number == 200:
            return issue_200
        return None

    def mock_flow_context_resolver(
        issue_number: int,
    ) -> tuple[str, dict[str, object] | None]:
        return (f"task/issue-{issue_number}", None)

    def mock_queue_selector(
        issues: list[IssueInfo],
        trigger_state: IssueState,
        config: OrchestraConfig,
        github: GitHubClient,
        store: SQLiteClient,
        flow_manager: FlowManagerProtocol,
        qualify_gate: QualifyGateService,
        supervisor_label: str,
    ) -> list[IssueInfo]:
        """Only returns issue #200, not #100."""
        # Suppress unused parameter warnings
        _ = config, github, store, flow_manager, qualify_gate, supervisor_label

        return [
            i
            for i in issues
            if (trigger_state in i.labels or trigger_state.to_label() in i.labels)
            and i.number == 200
        ]

    # Mock issue collector factory to only return issue #200
    mock_issue_collector = MagicMock()
    mock_issue_collector.collect_open_issues = MagicMock(return_value=[issue_200])

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
        flow_context_resolver=mock_flow_context_resolver,
        queue_selector=mock_queue_selector,
        issue_collector_factory=lambda: mock_issue_collector,
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

    # Trigger recollection (real implementation will preserve in-flight entries)
    await coordinator.force_recollect_queue()

    # Verify in-flight entry preserved
    assert coordinator._frozen_queue is not None
    numbers = [e.issue_number for e in coordinator._frozen_queue]
    assert 100 in numbers, "In-flight entry should be preserved"
    assert 200 in numbers, "Fresh entry should be added"

    # Verify waiting_state unchanged
    entry_100 = next(e for e in coordinator._frozen_queue if e.issue_number == 100)
    assert entry_100.waiting_state == "ready", "Waiting state should not be modified"


@pytest.mark.asyncio
async def test_disabled_config_skips_recollect(
    temp_store: SQLiteClient,
    monkeypatch: MonkeyPatch,
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
        manager_usernames=("manager-bot",),
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

    def mock_flow_context_resolver(
        issue_number: int,
    ) -> tuple[str, dict[str, object] | None]:
        return (f"task/issue-{issue_number}", None)

    def mock_queue_selector(
        issues: list[IssueInfo],
        trigger_state: IssueState,
        config: OrchestraConfig,
        github: GitHubClient,
        store: SQLiteClient,
        flow_manager: FlowManagerProtocol,
        qualify_gate: QualifyGateService,
        supervisor_label: str,
    ) -> list[IssueInfo]:
        """Empty queue selector for disabled config test."""
        # Suppress unused parameter warnings
        _ = (
            issues,
            trigger_state,
            config,
            github,
            store,
            flow_manager,
            qualify_gate,
            supervisor_label,
        )

        return []

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
        flow_context_resolver=mock_flow_context_resolver,
        queue_selector=mock_queue_selector,
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
