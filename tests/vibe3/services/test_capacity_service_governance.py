"""Tests for CapacityService governance and supervisor role support.

Tests cover:
- Global capacity pool shared across all roles
- In-flight dispatch tracking per role
- Capacity status reporting
- Full dispatch lifecycle
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.execution.capacity_service import CapacityService
from vibe3.models.orchestra_config import OrchestraConfig


@pytest.fixture()
def store(tmp_path: Path) -> SQLiteClient:
    return SQLiteClient(db_path=str(tmp_path / "capacity.db"))


@pytest.fixture()
def backend() -> MagicMock:
    mock = MagicMock()
    mock.has_tmux_session.return_value = True
    return mock


@pytest.fixture()
def config() -> MagicMock:
    cfg = MagicMock(spec=OrchestraConfig)
    # Global capacity configuration
    cfg.max_concurrent_flows = 3  # shared across all roles
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
    """can_dispatch returns False for governance when global pool is full."""
    with patch.object(service._registry, "count_live_worker_sessions", return_value=3):
        # 3 live == max_concurrent_flows, global pool full
        assert service.can_dispatch("governance", 2) is False


def test_can_dispatch_governance_accounts_for_in_flight(
    service: CapacityService,
) -> None:
    """can_dispatch considers in-flight dispatches in global pool."""
    # Fill 3 slots via in-flight
    service.mark_in_flight("governance", 1)
    service.mark_in_flight("governance", 2)
    service.mark_in_flight("governance", 3)

    with patch.object(service._registry, "count_live_worker_sessions", return_value=0):
        assert service.can_dispatch("governance", 4) is False


def test_governance_shares_global_pool_with_manager(
    service: CapacityService,
) -> None:
    """Governance and manager share the same global capacity pool."""
    # Fill global pool via manager in-flight
    service.mark_in_flight("manager", 10)
    service.mark_in_flight("manager", 20)

    with patch.object(service._registry, "count_live_worker_sessions", return_value=1):
        # Manager full (2 in-flight + 1 live = 3)
        assert service.can_dispatch("manager", 30) is False

        # Governance also blocked — same global pool
        assert service.can_dispatch("governance", 1) is False


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
    """can_dispatch returns False for supervisor when global pool is full."""
    with patch.object(service._registry, "count_live_worker_sessions", return_value=3):
        # 3 live == max_concurrent_flows, global pool full
        assert service.can_dispatch("supervisor", 99) is False


def test_can_dispatch_supervisor_accounts_for_in_flight(
    service: CapacityService,
) -> None:
    """can_dispatch considers in-flight dispatches in global pool."""
    # Fill 3 slots via supervisor in-flight
    service.mark_in_flight("supervisor", 10)
    service.mark_in_flight("supervisor", 20)
    service.mark_in_flight("supervisor", 30)

    with patch.object(service._registry, "count_live_worker_sessions", return_value=0):
        assert service.can_dispatch("supervisor", 40) is False


def test_supervisor_shares_global_pool_with_manager(
    service: CapacityService,
) -> None:
    """Supervisor and manager share the same global capacity pool."""
    # Fill global pool via manager
    service.mark_in_flight("manager", 10)
    service.mark_in_flight("manager", 20)
    with patch.object(service._registry, "count_live_worker_sessions", return_value=1):
        # Manager at capacity (2 in-flight + 1 live = 3)
        assert service.can_dispatch("manager", 30) is False

        # Supervisor also blocked — same global pool
        assert service.can_dispatch("supervisor", 42) is False


def test_supervisor_shares_global_pool_with_governance(
    service: CapacityService,
) -> None:
    """Supervisor and governance share the same global capacity pool."""
    # Fill 3 slots via governance
    service.mark_in_flight("governance", 1)
    service.mark_in_flight("governance", 2)
    service.mark_in_flight("governance", 3)
    with patch.object(service._registry, "count_live_worker_sessions", return_value=0):
        # Governance at capacity
        assert service.can_dispatch("governance", 4) is False

        # Supervisor also blocked — same global pool
        assert service.can_dispatch("supervisor", 42) is False


# --- Multi-role capacity isolation ---


def test_all_roles_share_global_capacity_pool(
    service: CapacityService,
) -> None:
    """All roles share a single global capacity pool."""
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
    assert status["max_capacity"] == 3  # global pool
    assert status["remaining"] == 2  # 3 - 0 - 1 = 2


def test_get_capacity_status_supervisor(
    service: CapacityService,
) -> None:
    """get_capacity_status returns correct snapshot for supervisor."""
    service.mark_in_flight("supervisor", 10)
    with patch.object(service._registry, "count_live_worker_sessions", return_value=1):
        status = service.get_capacity_status("supervisor")

    assert status["active_count"] == 1
    assert status["in_flight_count"] == 1
    assert status["max_capacity"] == 3  # global pool
    assert status["remaining"] == 1  # 3 - 1 - 1 = 1


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
