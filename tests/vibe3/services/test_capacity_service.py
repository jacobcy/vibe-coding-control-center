"""Tests for CapacityService."""

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
    cfg.max_concurrent_flows = 3
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
        assert service.can_dispatch("manager") is True


def test_can_dispatch_rejects_when_at_max(
    service: CapacityService,
) -> None:
    """can_dispatch returns False when live sessions == max_concurrent_flows."""
    with patch.object(service._registry, "count_live_worker_sessions", return_value=3):
        assert service.can_dispatch("manager") is False


def test_can_dispatch_with_zero_live_sessions(
    service: CapacityService,
) -> None:
    """can_dispatch returns True when no live sessions."""
    with patch.object(service._registry, "count_live_worker_sessions", return_value=0):
        assert service.can_dispatch("manager") is True


def test_can_dispatch_exact_boundary(
    service: CapacityService,
) -> None:
    """can_dispatch returns True when exactly one slot remaining."""
    # 2 live + 0 in_flight = 2 < max(3), remaining = 1
    with patch.object(service._registry, "count_live_worker_sessions", return_value=2):
        assert service.can_dispatch("manager") is True


# --- get_capacity_status ---


def test_get_capacity_status(
    service: CapacityService,
) -> None:
    """get_capacity_status returns correct capacity information."""
    with patch.object(service._registry, "count_live_worker_sessions", return_value=2):
        status = service.get_capacity_status("manager")
        assert status["active_count"] == 2
        assert status["max_capacity"] == 3
        assert status["remaining"] == 1
