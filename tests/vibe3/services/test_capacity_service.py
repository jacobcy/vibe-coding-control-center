"""Tests for CapacityService."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.execution.capacity_service import CapacityService
from vibe3.models.orchestra_config import OrchestraConfig


@pytest.fixture(autouse=True)
def cleanup_capacity_state():
    """Auto-cleanup class-level shared state after each test.

    CapacityService uses a class-level _shared_in_flight_dispatches dict
    for in-flight dispatch tracking. This fixture ensures test isolation
    by clearing the state after each test, preventing cross-test pollution.
    """
    yield
    CapacityService._shared_in_flight_dispatches.clear()


@pytest.fixture()
def store(tmp_path: Path) -> SQLiteClient:
    return SQLiteClient(db_path=str(tmp_path / "capacity.db"))


@pytest.fixture()
def backend() -> MagicMock:
    mock = MagicMock()
    mock.has_tmux_session.return_value = True
    mock.has_tmux_session_prefix.return_value = True
    return mock


@pytest.fixture()
def config() -> MagicMock:
    cfg = MagicMock(spec=OrchestraConfig)
    cfg.max_concurrent_flows = 3
    cfg.governance_max_concurrent = 1
    cfg.supervisor_max_concurrent = 2
    return cfg


@pytest.fixture()
def service(
    config: MagicMock, store: SQLiteClient, backend: MagicMock
) -> CapacityService:
    return CapacityService(config, store, backend)


# --- can_dispatch ---


def test_can_dispatch_when_capacity_available(
    service: CapacityService,
) -> None:
    """can_dispatch returns True when capacity is available."""
    with patch.object(service._registry, "count_live_worker_sessions", return_value=1):
        assert service.can_dispatch("manager", 42) is True


def test_can_dispatch_rejects_when_at_max(
    service: CapacityService,
) -> None:
    """can_dispatch returns False when live sessions == max_concurrent_flows."""
    with patch.object(service._registry, "count_live_worker_sessions", return_value=3):
        assert service.can_dispatch("manager", 42) is False


def test_can_dispatch_accounts_for_in_flight(
    service: CapacityService,
) -> None:
    """can_dispatch considers in-flight dispatches toward capacity."""
    service.mark_in_flight("manager", 10)
    service.mark_in_flight("manager", 20)

    # 2 in-flight + 1 live = 3 == max_concurrent_flows
    with patch.object(service._registry, "count_live_worker_sessions", return_value=1):
        assert service.can_dispatch("manager", 42) is False


def test_can_dispatch_with_zero_live_sessions(
    service: CapacityService,
) -> None:
    """can_dispatch returns True when no live sessions or in-flight."""
    with patch.object(service._registry, "count_live_worker_sessions", return_value=0):
        assert service.can_dispatch("manager", 1) is True


def test_can_dispatch_exact_boundary(
    service: CapacityService,
) -> None:
    """can_dispatch returns True when exactly one slot remaining."""
    # 2 live + 0 in_flight = 2 < max(3), remaining = 1
    with patch.object(service._registry, "count_live_worker_sessions", return_value=2):
        assert service.can_dispatch("manager", 99) is True


# --- mark_in_flight / prune_in_flight ---


def test_mark_in_flight_tracks_issues(
    service: CapacityService,
) -> None:
    """mark_in_flight adds issue to in-flight set for role."""
    service.mark_in_flight("manager", 10)
    assert 10 in service.in_flight_dispatches["manager"]

    service.mark_in_flight("manager", 20)
    assert 20 in service.in_flight_dispatches["manager"]
    assert len(service.in_flight_dispatches["manager"]) == 2


def test_prune_in_flight_removes_completed(
    service: CapacityService,
) -> None:
    """prune_in_flight removes issues from in-flight set for role."""
    service.mark_in_flight("manager", 10)
    service.mark_in_flight("manager", 20)
    service.mark_in_flight("manager", 30)

    service.prune_in_flight("manager", {10, 30})
    assert 10 not in service.in_flight_dispatches["manager"]
    assert 30 not in service.in_flight_dispatches["manager"]
    assert 20 in service.in_flight_dispatches["manager"]


def test_prune_in_flight_ignores_nonexistent(
    service: CapacityService,
) -> None:
    """prune_in_flight safely ignores issues not in set."""
    service.mark_in_flight("manager", 10)
    service.prune_in_flight("manager", {99})  # not in set
    assert 10 in service.in_flight_dispatches["manager"]


def test_mark_in_flight_idempotent(
    service: CapacityService,
) -> None:
    """Marking same issue twice is idempotent."""
    service.mark_in_flight("manager", 10)
    service.mark_in_flight("manager", 10)
    assert len(service.in_flight_dispatches["manager"]) == 1


# --- get_capacity_status ---


def test_get_capacity_status(
    service: CapacityService,
) -> None:
    """get_capacity_status returns correct snapshot."""
    service.mark_in_flight("manager", 5)
    with patch.object(service._registry, "count_live_worker_sessions", return_value=1):
        status = service.get_capacity_status("manager")

    assert status["active_count"] == 1
    assert status["in_flight_count"] == 1
    assert status["max_capacity"] == 3
    assert status["remaining"] == 1


def test_get_capacity_status_zero_remaining(
    service: CapacityService,
) -> None:
    """get_capacity_status shows 0 remaining when at capacity."""
    with patch.object(service._registry, "count_live_worker_sessions", return_value=3):
        status = service.get_capacity_status("manager")

    assert status["remaining"] == 0
    assert status["active_count"] == 3
    assert status["max_capacity"] == 3


# --- integration: can_dispatch respects full lifecycle ---


def test_full_dispatch_lifecycle(
    service: CapacityService,
) -> None:
    """Simulate a full dispatch lifecycle: check -> mark -> prune."""
    with patch.object(service._registry, "count_live_worker_sessions", return_value=0):
        # Step 1: Check capacity
        assert service.can_dispatch("manager", 42) is True

        # Step 2: Mark in-flight
        service.mark_in_flight("manager", 42)
        assert 42 in service.in_flight_dispatches["manager"]

        # Step 3: After dispatch completes, prune
        service.prune_in_flight("manager", {42})
        assert 42 not in service.in_flight_dispatches["manager"]

        # Step 4: Capacity is available again
        assert service.can_dispatch("manager", 42) is True


# --- multi-role tests ---


def test_can_dispatch_separates_roles(
    service: CapacityService,
) -> None:
    """Capacity is tracked separately per role."""
    # Manager at capacity
    service.mark_in_flight("manager", 10)
    service.mark_in_flight("manager", 20)
    with patch.object(service._registry, "count_live_worker_sessions", return_value=1):
        # Manager full (2 in-flight + 1 live = 3)
        assert service.can_dispatch("manager", 30) is False

        # Planner still has capacity
        assert service.can_dispatch("planner", 40) is True


def test_mark_in_flight_separates_roles(
    service: CapacityService,
) -> None:
    """In-flight dispatches are tracked separately per role."""
    service.mark_in_flight("manager", 10)
    service.mark_in_flight("planner", 20)

    # Separate tracking
    assert 10 in service.in_flight_dispatches["manager"]
    assert 20 in service.in_flight_dispatches["planner"]
    assert 10 not in service.in_flight_dispatches.get("planner", set())
    assert 20 not in service.in_flight_dispatches.get("manager", set())


def test_in_flight_is_shared_across_instances_for_same_db(
    config: MagicMock,
    store: SQLiteClient,
    backend: MagicMock,
) -> None:
    """Multiple CapacityService instances over the same DB share in-flight truth."""
    first = CapacityService(config, store, backend)
    second = CapacityService(config, store, backend)

    first.mark_in_flight("manager", 42)

    assert 42 in second.in_flight_dispatches["manager"]

    second.prune_in_flight("manager", {42})
    assert 42 not in first.in_flight_dispatches["manager"]
