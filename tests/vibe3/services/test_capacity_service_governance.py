"""Tests for CapacityService governance and supervisor role support.

Tests cover:
- Governance role capacity control
- Supervisor role capacity control
- Per-role capacity configuration
- Live session count integration
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.services.capacity_service import CapacityService


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
    # Per-role capacity configuration
    cfg.max_concurrent_flows = 3  # default for manager
    cfg.governance_max_concurrent = 1
    cfg.supervisor_max_concurrent = 2
    return cfg


@pytest.fixture()
def service(
    config: MagicMock, store: SQLiteClient, backend: MagicMock
) -> CapacityService:
    return CapacityService(config, store, backend)


# --- Governance role capacity ---


def test_can_dispatch_governance_when_capacity_available(
    service: CapacityService,
) -> None:
    """can_dispatch returns True for governance when capacity available."""
    with patch.object(service._registry, "count_live_worker_sessions", return_value=0):
        assert service.can_dispatch("governance", 1) is True


def test_can_dispatch_governance_rejects_when_at_max(
    service: CapacityService,
) -> None:
    """can_dispatch returns False for governance when live sessions == max."""
    with patch.object(service._registry, "count_live_worker_sessions", return_value=1):
        # governance_max_concurrent = 1, so at capacity
        assert service.can_dispatch("governance", 2) is False


def test_can_dispatch_governance_accounts_for_in_flight(
    service: CapacityService,
) -> None:
    """can_dispatch considers in-flight dispatches for governance capacity."""
    service.mark_in_flight("governance", 1)

    # 1 in-flight + 0 live = 1 == governance_max_concurrent
    with patch.object(service._registry, "count_live_worker_sessions", return_value=0):
        assert service.can_dispatch("governance", 2) is False


def test_governance_capacity_independent_from_manager(
    service: CapacityService,
) -> None:
    """Governance capacity is independent from manager capacity."""
    # Fill manager capacity
    service.mark_in_flight("manager", 10)
    service.mark_in_flight("manager", 20)

    # Mock different live session counts for different roles
    def mock_count_sessions(role: str) -> int:
        if role == "manager":
            return 1
        elif role == "governance":
            return 0
        return 0

    with patch.object(
        service._registry, "count_live_worker_sessions", side_effect=mock_count_sessions
    ):
        # Manager at capacity (2 in-flight + 1 live = 3)
        assert service.can_dispatch("manager", 30) is False

        # Governance still has capacity (0 live + 0 in-flight = 0 < 1)
        assert service.can_dispatch("governance", 1) is True


# --- Supervisor role capacity ---


def test_can_dispatch_supervisor_when_capacity_available(
    service: CapacityService,
) -> None:
    """can_dispatch returns True for supervisor when capacity available."""
    with patch.object(service._registry, "count_live_worker_sessions", return_value=0):
        assert service.can_dispatch("supervisor", 42) is True


def test_can_dispatch_supervisor_rejects_when_at_max(
    service: CapacityService,
) -> None:
    """can_dispatch returns False for supervisor when live sessions == max."""
    with patch.object(service._registry, "count_live_worker_sessions", return_value=2):
        # supervisor_max_concurrent = 2, so at capacity
        assert service.can_dispatch("supervisor", 99) is False


def test_can_dispatch_supervisor_accounts_for_in_flight(
    service: CapacityService,
) -> None:
    """can_dispatch considers in-flight dispatches for supervisor capacity."""
    service.mark_in_flight("supervisor", 10)
    service.mark_in_flight("supervisor", 20)

    # 2 in-flight + 0 live = 2 == supervisor_max_concurrent
    with patch.object(service._registry, "count_live_worker_sessions", return_value=0):
        assert service.can_dispatch("supervisor", 30) is False


def test_supervisor_capacity_independent_from_manager(
    service: CapacityService,
) -> None:
    """Supervisor capacity is independent from manager capacity."""
    # Fill manager capacity
    service.mark_in_flight("manager", 10)
    service.mark_in_flight("manager", 20)
    with patch.object(service._registry, "count_live_worker_sessions", return_value=1):
        # Manager at capacity (2 in-flight + 1 live = 3)
        assert service.can_dispatch("manager", 30) is False

        # Supervisor still has capacity
        assert service.can_dispatch("supervisor", 42) is True


def test_supervisor_capacity_independent_from_governance(
    service: CapacityService,
) -> None:
    """Supervisor capacity is independent from governance capacity."""
    # Fill governance capacity
    service.mark_in_flight("governance", 1)
    with patch.object(service._registry, "count_live_worker_sessions", return_value=0):
        # Governance at capacity
        assert service.can_dispatch("governance", 2) is False

        # Supervisor still has capacity
        assert service.can_dispatch("supervisor", 42) is True


# --- Multi-role capacity isolation ---


def test_all_roles_use_separate_capacity_pools(
    service: CapacityService,
) -> None:
    """Each role has its own capacity pool."""
    with patch.object(service._registry, "count_live_worker_sessions", return_value=0):
        # All roles should have capacity initially
        assert service.can_dispatch("manager", 1) is True
        assert service.can_dispatch("governance", 1) is True
        assert service.can_dispatch("supervisor", 1) is True
        assert service.can_dispatch("planner", 1) is True
        assert service.can_dispatch("executor", 1) is True
        assert service.can_dispatch("reviewer", 1) is True


def test_mark_in_flight_separates_governance_and_supervisor(
    service: CapacityService,
) -> None:
    """In-flight dispatches are tracked separately for governance and supervisor."""
    service.mark_in_flight("governance", 1)
    service.mark_in_flight("supervisor", 42)

    # Separate tracking
    assert 1 in service.in_flight_dispatches["governance"]
    assert 42 in service.in_flight_dispatches["supervisor"]
    assert 1 not in service.in_flight_dispatches.get("supervisor", set())
    assert 42 not in service.in_flight_dispatches.get("governance", set())


# --- Capacity status for governance and supervisor ---


def test_get_capacity_status_governance(
    service: CapacityService,
) -> None:
    """get_capacity_status returns correct snapshot for governance."""
    service.mark_in_flight("governance", 1)
    with patch.object(service._registry, "count_live_worker_sessions", return_value=0):
        status = service.get_capacity_status("governance")

    assert status["active_count"] == 0
    assert status["in_flight_count"] == 1
    assert status["max_capacity"] == 1
    assert status["remaining"] == 0


def test_get_capacity_status_supervisor(
    service: CapacityService,
) -> None:
    """get_capacity_status returns correct snapshot for supervisor."""
    service.mark_in_flight("supervisor", 10)
    with patch.object(service._registry, "count_live_worker_sessions", return_value=1):
        status = service.get_capacity_status("supervisor")

    assert status["active_count"] == 1
    assert status["in_flight_count"] == 1
    assert status["max_capacity"] == 2
    assert status["remaining"] == 0


# --- Full lifecycle for governance and supervisor ---


def test_full_dispatch_lifecycle_governance(
    service: CapacityService,
) -> None:
    """Simulate a full dispatch lifecycle for governance."""
    with patch.object(service._registry, "count_live_worker_sessions", return_value=0):
        # Step 1: Check capacity
        assert service.can_dispatch("governance", 1) is True

        # Step 2: Mark in-flight
        service.mark_in_flight("governance", 1)
        assert 1 in service.in_flight_dispatches["governance"]

        # Step 3: After dispatch completes, prune
        service.prune_in_flight("governance", {1})
        assert 1 not in service.in_flight_dispatches["governance"]

        # Step 4: Capacity is available again
        assert service.can_dispatch("governance", 2) is True


def test_full_dispatch_lifecycle_supervisor(
    service: CapacityService,
) -> None:
    """Simulate a full dispatch lifecycle for supervisor."""
    with patch.object(service._registry, "count_live_worker_sessions", return_value=0):
        # Step 1: Check capacity
        assert service.can_dispatch("supervisor", 42) is True

        # Step 2: Mark in-flight
        service.mark_in_flight("supervisor", 42)
        assert 42 in service.in_flight_dispatches["supervisor"]

        # Step 3: After dispatch completes, prune
        service.prune_in_flight("supervisor", {42})
        assert 42 not in service.in_flight_dispatches["supervisor"]

        # Step 4: Capacity is available again
        assert service.can_dispatch("supervisor", 99) is True
