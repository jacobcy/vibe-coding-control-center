"""Tests for pool exhaustion auto-stop logic."""

import pytest

from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.orchestra.domain_types import ServiceBase
from vibe3.runtime.heartbeat import HeartbeatServer


class _MockService(ServiceBase):
    def __init__(self) -> None:
        self.ticks: int = 0

    async def on_tick(self, tick_id: int = 0) -> None:
        self.ticks += 1


def _config() -> OrchestraConfig:
    return OrchestraConfig(polling_interval=900, max_concurrent_flows=3)


class MockDispatchCoordinator:
    """Mock coordinator for pool exhaustion testing."""

    def __init__(self, is_paused: bool = False) -> None:
        self._is_paused = is_paused

    def is_dispatch_paused(self) -> bool:
        """Return mocked pause state."""
        return self._is_paused


@pytest.mark.asyncio
async def test_pool_exhaustion_counter_increments(monkeypatch) -> None:
    """Counter should increment when pool is exhausted."""
    coordinator = MockDispatchCoordinator(is_paused=True)
    server = HeartbeatServer(
        OrchestraConfig(
            polling_interval=1,
            max_concurrent_flows=3,
            auto_stop_on_exhaustion=True,
            exhaustion_threshold_ticks=10,
        ),
        dispatch_coordinator=coordinator,
    )
    svc = _MockService()
    server.register(svc)

    events: list[str] = []
    tick_count = 0

    def _capture(domain: str, message: str, **kwargs) -> None:
        events.append(f"{domain}:{message}")

    async def _sleep_once(_seconds: float) -> None:
        nonlocal tick_count
        tick_count += 1
        if tick_count >= 6:
            server.stop()

    monkeypatch.setattr("vibe3.runtime.heartbeat.append_orchestra_event", _capture)
    monkeypatch.setattr(
        "vibe3.runtime.pool_exhaustion.append_orchestra_event", _capture
    )
    monkeypatch.setattr("vibe3.runtime.heartbeat.asyncio.sleep", _sleep_once)
    server._running = True

    await server._tick_loop()

    assert server._exhausted_ticks == 5
    exhaustion_events = [e for e in events if "pool exhausted" in e]
    assert len(exhaustion_events) >= 5


@pytest.mark.asyncio
async def test_pool_exhaustion_counter_resets(monkeypatch) -> None:
    """Counter should reset when pool has candidates."""
    coordinator = MockDispatchCoordinator(is_paused=False)
    server = HeartbeatServer(
        OrchestraConfig(
            polling_interval=1,
            max_concurrent_flows=3,
            auto_stop_on_exhaustion=True,
            exhaustion_threshold_ticks=5,
        ),
        dispatch_coordinator=coordinator,
    )
    server._exhausted_ticks = 4

    svc = _MockService()
    server.register(svc)

    events: list[str] = []
    tick_count = 0

    def _capture(domain: str, message: str, **kwargs) -> None:
        events.append(f"{domain}:{message}")

    async def _sleep_once(_seconds: float) -> None:
        nonlocal tick_count
        tick_count += 1
        if tick_count >= 2:
            server.stop()

    monkeypatch.setattr("vibe3.runtime.heartbeat.append_orchestra_event", _capture)
    monkeypatch.setattr("vibe3.runtime.heartbeat.asyncio.sleep", _sleep_once)
    server._running = True

    await server._tick_loop()

    assert server._exhausted_ticks == 0


@pytest.mark.asyncio
async def test_pool_exhaustion_stops_at_threshold(monkeypatch) -> None:
    """Server should stop when exhaustion threshold reached."""
    coordinator = MockDispatchCoordinator(is_paused=True)
    server = HeartbeatServer(
        OrchestraConfig(
            polling_interval=1,
            max_concurrent_flows=3,
            auto_stop_on_exhaustion=True,
            exhaustion_threshold_ticks=3,
        ),
        dispatch_coordinator=coordinator,
    )
    svc = _MockService()
    server.register(svc)

    events: list[str] = []

    def _capture(domain: str, message: str, **kwargs) -> None:
        events.append(f"{domain}:{message}")

    async def _no_wait(_seconds: float) -> None:
        return None

    monkeypatch.setattr("vibe3.runtime.heartbeat.append_orchestra_event", _capture)
    monkeypatch.setattr(
        "vibe3.runtime.pool_exhaustion.append_orchestra_event", _capture
    )
    monkeypatch.setattr("vibe3.runtime.heartbeat.asyncio.sleep", _no_wait)
    server._running = True

    await server._tick_loop()

    assert server.running is False
    assert server._exhausted_ticks == 3
    assert any("stopping server" in e for e in events)


@pytest.mark.asyncio
async def test_pool_exhaustion_no_coordinator_returns_false() -> None:
    """Should return False when coordinator is None (no crash)."""
    from vibe3.runtime.pool_exhaustion import is_pool_exhausted

    assert is_pool_exhausted(None) is False


@pytest.mark.asyncio
async def test_pool_exhaustion_disabled_does_not_check(monkeypatch) -> None:
    """Should not check exhaustion when auto_stop_on_exhaustion=False."""
    coordinator = MockDispatchCoordinator(is_paused=True)
    server = HeartbeatServer(
        OrchestraConfig(
            polling_interval=1,
            max_concurrent_flows=3,
            auto_stop_on_exhaustion=False,
            exhaustion_threshold_ticks=3,
        ),
        dispatch_coordinator=coordinator,
    )
    svc = _MockService()
    server.register(svc)

    events: list[str] = []
    tick_count = 0

    def _capture(domain: str, message: str, **kwargs) -> None:
        events.append(f"{domain}:{message}")

    async def _sleep_once(_seconds: float) -> None:
        nonlocal tick_count
        tick_count += 1
        if tick_count >= 5:
            server.stop()

    monkeypatch.setattr("vibe3.runtime.heartbeat.append_orchestra_event", _capture)
    monkeypatch.setattr("vibe3.runtime.heartbeat.asyncio.sleep", _sleep_once)
    server._running = True

    await server._tick_loop()

    assert server._exhausted_ticks == 0
    assert not any("pool exhausted" in e for e in events)
    assert tick_count == 5
