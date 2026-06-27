"""Tests for pool exhaustion auto-stop logic."""

import pytest

from vibe3.models.orchestra_config import OrchestraConfig, PoolExhaustionConfig
from vibe3.runtime.heartbeat import HeartbeatServer
from vibe3.runtime.protocols import ServiceBase


class _MockService(ServiceBase):
    def __init__(self) -> None:
        self.ticks: int = 0

    async def on_tick(self, tick_id: int = 0) -> None:
        self.ticks += 1


def _config() -> OrchestraConfig:
    return OrchestraConfig(
        polling_interval=900,
        max_concurrent_flows=3,
        pool_exhaustion=PoolExhaustionConfig(),
    )


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
            pool_exhaustion=PoolExhaustionConfig(
                auto_stop_on_exhaustion=True,
                exhaustion_threshold_ticks=10,
            ),
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

    # Tick progression with cold-start fix:
    # - tick 1: cold-start sets to 1, check_pool_exhaustion increments to 2
    # - tick 2-5: check_pool_exhaustion increments each (2 + 4 = 6)
    # - sleep(6) triggers stop() before tick 6 runs
    # Final counter: 6 (cold-start initialization + 5 increments)
    assert server._exhausted_ticks == 6
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
            pool_exhaustion=PoolExhaustionConfig(
                auto_stop_on_exhaustion=True,
                exhaustion_threshold_ticks=5,
            ),
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
    """Server should enter sleep mode at threshold, then stop after max sleep cycles."""
    coordinator = MockDispatchCoordinator(is_paused=True)
    server = HeartbeatServer(
        OrchestraConfig(
            polling_interval=1,
            max_concurrent_flows=3,
            pool_exhaustion=PoolExhaustionConfig(
                auto_stop_on_exhaustion=True,
                exhaustion_threshold_ticks=3,
                sleep_check_interval_ticks=2,  # Wake up every 2 ticks
                max_sleep_cycles=2,  # Stop after 2 wake-ups
            ),
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
    # Tick progression: 1,2,3(threshold→sleep),4(wake-up #1),5,6(wake-up #2→stop)
    # exhausted_ticks should be at wake-up tick (6)
    assert server._exhausted_ticks >= 3
    assert any("entering sleep mode" in e for e in events)
    assert any("stopping server" in e for e in events)


@pytest.mark.asyncio
async def test_pool_exhaustion_no_coordinator_no_crash() -> None:
    """Should not crash when coordinator is None."""
    from vibe3.runtime.pool_exhaustion import check_pool_exhaustion

    config = _config()
    stop_called = False

    def _stop() -> None:
        nonlocal stop_called
        stop_called = True

    result = check_pool_exhaustion(
        None, config, exhausted_ticks=5, sleep_cycles=0, stop_callback=_stop
    )
    assert result == (0, 0)
    assert not stop_called


@pytest.mark.asyncio
async def test_pool_exhaustion_disabled_does_not_check(monkeypatch) -> None:
    """Should not check exhaustion when auto_stop_on_exhaustion=False."""
    coordinator = MockDispatchCoordinator(is_paused=True)
    server = HeartbeatServer(
        OrchestraConfig(
            polling_interval=1,
            max_concurrent_flows=3,
            pool_exhaustion=PoolExhaustionConfig(
                auto_stop_on_exhaustion=False,
                exhaustion_threshold_ticks=3,
            ),
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


# Sleep mode tests

@pytest.mark.asyncio
async def test_sleep_mode_entry_at_threshold(monkeypatch) -> None:
    """Should enter sleep mode at threshold instead of immediate stop."""
    from vibe3.runtime.pool_exhaustion import check_pool_exhaustion

    coordinator = MockDispatchCoordinator(is_paused=True)
    config = OrchestraConfig(
        polling_interval=1,
        max_concurrent_flows=3,
        pool_exhaustion=PoolExhaustionConfig(
            auto_stop_on_exhaustion=True,
            exhaustion_threshold_ticks=4,
            sleep_check_interval_ticks=10,
            max_sleep_cycles=3,
        ),
    )

    events: list[str] = []

    def _capture(domain: str, message: str, **kwargs) -> None:
        events.append(f"{domain}:{message}")

    stop_called = False

    def _stop() -> None:
        nonlocal stop_called
        stop_called = True

    monkeypatch.setattr(
        "vibe3.runtime.pool_exhaustion.append_orchestra_event", _capture
    )

    # Simulate reaching threshold
    exhausted_ticks, sleep_cycles = check_pool_exhaustion(
        coordinator, config, exhausted_ticks=3, sleep_cycles=0, stop_callback=_stop
    )

    assert exhausted_ticks == 4
    assert sleep_cycles == 0
    assert not stop_called
    assert any("entering sleep mode" in e for e in events)


@pytest.mark.asyncio
async def test_sleep_mode_wakeup_increments_cycles(monkeypatch) -> None:
    """Wake-up ticks should increment sleep_cycles."""
    from vibe3.runtime.pool_exhaustion import check_pool_exhaustion

    coordinator = MockDispatchCoordinator(is_paused=True)
    config = OrchestraConfig(
        polling_interval=1,
        max_concurrent_flows=3,
        pool_exhaustion=PoolExhaustionConfig(
            auto_stop_on_exhaustion=True,
            exhaustion_threshold_ticks=4,
            sleep_check_interval_ticks=10,
            max_sleep_cycles=3,
        ),
    )

    events: list[str] = []

    def _capture(domain: str, message: str, **kwargs) -> None:
        events.append(f"{domain}:{message}")

    stop_called = False

    def _stop() -> None:
        nonlocal stop_called
        stop_called = True

    monkeypatch.setattr(
        "vibe3.runtime.pool_exhaustion.append_orchestra_event", _capture
    )

    # Simulate wake-up tick (exhausted_ticks=10, which is 1st wake-up)
    exhausted_ticks, sleep_cycles = check_pool_exhaustion(
        coordinator, config, exhausted_ticks=9, sleep_cycles=0, stop_callback=_stop
    )

    assert exhausted_ticks == 10
    assert sleep_cycles == 1
    assert not stop_called
    assert any("sleep wake-up #1" in e for e in events)


@pytest.mark.asyncio
async def test_sleep_mode_stop_at_max_cycles(monkeypatch) -> None:
    """Should stop after max_sleep_cycles wake-ups."""
    from vibe3.runtime.pool_exhaustion import check_pool_exhaustion

    coordinator = MockDispatchCoordinator(is_paused=True)
    config = OrchestraConfig(
        polling_interval=1,
        max_concurrent_flows=3,
        pool_exhaustion=PoolExhaustionConfig(
            auto_stop_on_exhaustion=True,
            exhaustion_threshold_ticks=4,
            sleep_check_interval_ticks=10,
            max_sleep_cycles=2,
        ),
    )

    events: list[str] = []

    def _capture(domain: str, message: str, **kwargs) -> None:
        events.append(f"{domain}:{message}")

    stop_called = False

    def _stop() -> None:
        nonlocal stop_called
        stop_called = True

    monkeypatch.setattr(
        "vibe3.runtime.pool_exhaustion.append_orchestra_event", _capture
    )

    # Simulate 2nd wake-up (should trigger stop)
    exhausted_ticks, sleep_cycles = check_pool_exhaustion(
        coordinator, config, exhausted_ticks=19, sleep_cycles=1, stop_callback=_stop
    )

    assert exhausted_ticks == 20
    assert sleep_cycles == 2
    assert stop_called
    assert any("stopping server" in e for e in events)


@pytest.mark.asyncio
async def test_sleep_mode_resets_on_unpause() -> None:
    """Both counters should reset when dispatch unpauses."""
    from vibe3.runtime.pool_exhaustion import check_pool_exhaustion

    coordinator = MockDispatchCoordinator(is_paused=False)
    config = OrchestraConfig(
        polling_interval=1,
        max_concurrent_flows=3,
        pool_exhaustion=PoolExhaustionConfig(
            auto_stop_on_exhaustion=True,
            exhaustion_threshold_ticks=4,
            sleep_check_interval_ticks=10,
            max_sleep_cycles=3,
        ),
    )

    stop_called = False

    def _stop() -> None:
        nonlocal stop_called
        stop_called = True

    # Start from non-zero counters
    exhausted_ticks, sleep_cycles = check_pool_exhaustion(
        coordinator, config, exhausted_ticks=15, sleep_cycles=2, stop_callback=_stop
    )

    assert exhausted_ticks == 0
    assert sleep_cycles == 0
    assert not stop_called


@pytest.mark.asyncio
async def test_sleep_mode_max_cycles_zero_never_stops(monkeypatch) -> None:
    """max_sleep_cycles=0 should never stop the server."""
    from vibe3.runtime.pool_exhaustion import check_pool_exhaustion

    coordinator = MockDispatchCoordinator(is_paused=True)
    config = OrchestraConfig(
        polling_interval=1,
        max_concurrent_flows=3,
        pool_exhaustion=PoolExhaustionConfig(
            auto_stop_on_exhaustion=True,
            exhaustion_threshold_ticks=4,
            sleep_check_interval_ticks=10,
            max_sleep_cycles=0,  # Never stop
        ),
    )

    events: list[str] = []

    def _capture(domain: str, message: str, **kwargs) -> None:
        events.append(f"{domain}:{message}")

    stop_called = False

    def _stop() -> None:
        nonlocal stop_called
        stop_called = True

    monkeypatch.setattr(
        "vibe3.runtime.pool_exhaustion.append_orchestra_event", _capture
    )

    # Simulate many wake-ups (should never stop)
    for i in range(1, 6):
        exhausted_ticks, sleep_cycles = check_pool_exhaustion(
            coordinator, config, exhausted_ticks=9 + i * 10, sleep_cycles=i - 1, stop_callback=_stop
        )
        assert exhausted_ticks == 10 + i * 10
        assert sleep_cycles == i
        assert not stop_called


@pytest.mark.asyncio
async def test_tick1_cold_start_paused(monkeypatch) -> None:
    """Cold-start block initializes counter to 1 BEFORE check_pool_exhaustion runs."""
    coordinator = MockDispatchCoordinator(is_paused=True)
    server = HeartbeatServer(
        OrchestraConfig(
            polling_interval=1,
            max_concurrent_flows=3,
            pool_exhaustion=PoolExhaustionConfig(
                auto_stop_on_exhaustion=True,
                exhaustion_threshold_ticks=10,  # High threshold to avoid early stop
                sleep_check_interval_ticks=20,  # Don't trigger wake-up during test
                max_sleep_cycles=5,
            ),
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
        # Run 3 ticks to verify cold-start initialization
        if tick_count >= 3:
            server.stop()

    monkeypatch.setattr("vibe3.runtime.heartbeat.append_orchestra_event", _capture)
    monkeypatch.setattr(
        "vibe3.runtime.pool_exhaustion.append_orchestra_event", _capture
    )
    monkeypatch.setattr("vibe3.runtime.heartbeat.asyncio.sleep", _sleep_once)
    server._running = True

    await server._tick_loop()

    # Tick progression:
    # - sleep(1) -> tick 1 runs (cold-start sets to 1, check_pool_exhaustion increments to 2)
    # - sleep(2) -> tick 2 runs (check_pool_exhaustion increments to 3)
    # - sleep(3) -> stop() called before tick 3 runs
    # Final counter: 3 (cold-start + 2 increments from check_pool_exhaustion)
    # If cold-start were dead code, counter would be 2 (only 2 increments from check_pool_exhaustion)
    assert server._exhausted_ticks == 3
    exhaustion_events = [e for e in events if "pool exhausted" in e]
    assert len(exhaustion_events) >= 2
