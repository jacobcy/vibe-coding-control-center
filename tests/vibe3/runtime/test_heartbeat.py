"""Tests for HeartbeatServer."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.orchestra.failed_gate import GateResult
from vibe3.runtime.heartbeat import HeartbeatServer
from vibe3.runtime.service_protocol import ServiceBase


def _config() -> OrchestraConfig:
    return OrchestraConfig(polling_interval=900, max_concurrent_flows=3)


class _MockService(ServiceBase):
    def __init__(self) -> None:
        self.ticks: int = 0

    async def on_tick(self, tick_id: int = 0) -> None:
        self.ticks += 1


def test_register_service() -> None:
    server = HeartbeatServer(_config())
    svc = _MockService()
    server.register(svc)
    assert svc in server._services
    assert "MockService" in server.service_names[0]


@pytest.mark.asyncio
async def test_tick_calls_on_tick_for_all_services() -> None:
    server = HeartbeatServer(_config())
    svc1 = _MockService()
    svc2 = _MockService()
    server.register(svc1)
    server.register(svc2)

    await server._tick_service(svc1, 1)
    await server._tick_service(svc2, 1)

    assert svc1.ticks == 1
    assert svc2.ticks == 1


def test_run_separator_appends_instead_of_truncating(
    tmp_path: Path, monkeypatch
) -> None:
    """Run separator should append to existing events.log, not overwrite it."""
    from vibe3.orchestra.logging import append_orchestra_run_separator

    # Clear any environment variables that might affect log directory
    monkeypatch.delenv("VIBE3_ASYNC_LOG_DIR", raising=False)
    monkeypatch.setenv("VIBE3_ORCHESTRA_EVENT_LOG", "1")
    log_path = tmp_path / "temp" / "logs" / "orchestra" / "events.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("old event from previous run\n", encoding="utf-8")
    append_orchestra_run_separator(repo_root=tmp_path, title="server run start")
    text = log_path.read_text()
    # Old event should still be present
    assert "old event from previous run" in text
    # New run separator should be appended
    assert "========== server run start @" in text


@pytest.mark.asyncio
async def test_tick_loop_writes_tick_separator_lines(monkeypatch) -> None:
    """Each tick should have a clear separator line for readability."""
    server = HeartbeatServer(
        OrchestraConfig(polling_interval=1, max_concurrent_flows=3)
    )
    svc = _MockService()
    server.register(svc)

    events: list[str] = []

    def _capture(domain: str, message: str, **kwargs) -> None:
        events.append(f"{domain}:{message}")

    calls = {"count": 0}

    async def _sleep_once(_seconds: float) -> None:
        calls["count"] += 1
        if calls["count"] >= 3:  # Run at least 2 ticks before stopping
            server.stop()

    monkeypatch.setattr("vibe3.runtime.heartbeat.append_orchestra_event", _capture)
    monkeypatch.setattr("vibe3.runtime.heartbeat.asyncio.sleep", _sleep_once)
    server._running = True

    await server._tick_loop()

    # Should have tick start markers (simplified format)
    assert any(
        "server:tick #1 start" in item for item in events
    ), f"Expected tick start marker, got: {events}"
    assert len(events) >= 4, f"Expected at least 4 events, got: {events}"


@pytest.mark.asyncio
async def test_tick_loop_logs_start_and_completion(monkeypatch) -> None:
    server = HeartbeatServer(
        OrchestraConfig(polling_interval=1, max_concurrent_flows=3)
    )
    svc = _MockService()
    server.register(svc)

    events: list[str] = []

    def _capture(domain: str, message: str, **kwargs) -> None:
        events.append(f"{domain}:{message}")

    calls = {"count": 0}

    async def _sleep_once(_seconds: float) -> None:
        calls["count"] += 1
        if calls["count"] >= 2:
            server.stop()

    monkeypatch.setattr("vibe3.runtime.heartbeat.append_orchestra_event", _capture)
    monkeypatch.setattr("vibe3.runtime.heartbeat.asyncio.sleep", _sleep_once)
    server._running = True

    await server._tick_loop()

    assert any("server:tick #1 start" == item for item in events)
    # Services list is DEBUG level, so not present in default log level
    assert any("server:tick #1 completed in " in item for item in events)


@pytest.mark.asyncio
async def test_tick_loop_ignores_failed_gate_and_still_ticks(monkeypatch) -> None:
    server = HeartbeatServer(
        OrchestraConfig(polling_interval=1, max_concurrent_flows=3)
    )
    svc = _MockService()
    server.register(svc)

    events: list[str] = []

    def _capture(domain: str, message: str, **kwargs) -> None:
        events.append(f"{domain}:{message}")

    calls = {"count": 0}

    async def _sleep_once(_seconds: float) -> None:
        calls["count"] += 1
        if calls["count"] >= 2:
            server.stop()

    mock_gate = MagicMock()
    mock_gate.check.return_value = GateResult.open_gate()
    server._failed_gate = mock_gate

    monkeypatch.setattr("vibe3.runtime.heartbeat.append_orchestra_event", _capture)
    monkeypatch.setattr("vibe3.runtime.heartbeat.asyncio.sleep", _sleep_once)
    server._running = True

    await server._tick_loop()

    assert svc.ticks == 1
    assert any("server:tick #1 start" == item for item in events)


@pytest.mark.asyncio
async def test_tick_loop_continues_when_error_cleanup_fails(monkeypatch) -> None:
    server = HeartbeatServer(
        OrchestraConfig(polling_interval=1, max_concurrent_flows=3)
    )
    svc = _MockService()
    server.register(svc)

    events: list[str] = []

    def _capture(domain: str, message: str, **kwargs) -> None:
        events.append(f"{domain}:{message}")

    calls = {"count": 0}

    async def _sleep_once(_seconds: float) -> None:
        calls["count"] += 1
        if calls["count"] >= 2:
            server.stop()

    cleanup_service = MagicMock()
    cleanup_service.cleanup_old_errors.side_effect = RuntimeError("db locked")

    monkeypatch.setattr("vibe3.runtime.heartbeat.append_orchestra_event", _capture)
    monkeypatch.setattr("vibe3.runtime.heartbeat.asyncio.sleep", _sleep_once)
    # Mock ErrorTrackingService at its actual module location
    monkeypatch.setattr(
        "vibe3.services.error_tracking_service.ErrorTrackingService.get_instance",
        staticmethod(lambda: cleanup_service),
    )
    server._running = True

    await server._tick_loop()

    assert svc.ticks == 1
    assert any(
        "server:tick #1 cleanup_old_errors failed: db locked" == item for item in events
    )


@pytest.mark.asyncio
async def test_tick_loop_stops_after_debug_max_ticks(monkeypatch) -> None:
    server = HeartbeatServer(
        OrchestraConfig(
            polling_interval=60,
            max_concurrent_flows=3,
            debug=True,
            debug_max_ticks=2,
        )
    )
    svc = _MockService()
    server.register(svc)

    events: list[str] = []

    def _capture(domain: str, message: str, **kwargs) -> None:
        events.append(f"{domain}:{message}")

    async def _no_wait(_seconds: float) -> None:
        return None

    monkeypatch.setattr("vibe3.runtime.heartbeat.append_orchestra_event", _capture)
    monkeypatch.setattr("vibe3.runtime.heartbeat.asyncio.sleep", _no_wait)
    server._running = True

    await server._tick_loop()

    assert server.running is False
    assert svc.ticks == 2
    assert any("server:tick #2 start" == item for item in events)
    assert any(
        "server:debug tick limit reached (2), stopping server" == item
        for item in events
    )


def test_set_shutdown_callback_invoked_on_cleanup() -> None:
    """_cleanup() must invoke the registered shutdown callback exactly once."""
    server = HeartbeatServer(_config())
    calls: list[str] = []
    server.set_shutdown_callback(lambda: calls.append("called"))

    server._cleanup()

    assert calls == ["called"], "shutdown callback was not invoked during _cleanup"


def test_shutdown_callback_exception_does_not_propagate() -> None:
    """A callback that raises must not crash _cleanup() (best-effort)."""
    server = HeartbeatServer(_config())
    server.set_shutdown_callback(lambda: 1 / 0)

    # Should not raise
    server._cleanup()


def test_no_shutdown_callback_cleanup_still_runs() -> None:
    """_cleanup() without a registered callback should not raise."""
    server = HeartbeatServer(_config())
    server._cleanup()  # must not raise


@pytest.mark.asyncio
async def test_tick_loop_triggers_cleanup_on_interval_tick(monkeypatch) -> None:
    """Cleanup should trigger on tick number that is a multiple of interval_ticks."""
    from vibe3.config.orchestra_config import PeriodicCheckConfig

    config = OrchestraConfig(
        polling_interval=1,
        max_concurrent_flows=3,
        periodic_check=PeriodicCheckConfig(interval_ticks=2),
    )
    server = HeartbeatServer(config)
    svc = _MockService()
    server.register(svc)

    events: list[str] = []
    cleanup_calls: list[int] = []

    def _capture(domain: str, message: str, **kwargs) -> None:
        events.append(f"{domain}:{message}")

    async def _sleep_once(_seconds: float) -> None:
        if len(cleanup_calls) >= 3:  # Run at least 3 ticks
            server.stop()

    async def _mock_cleanup(tick_number: int) -> None:
        cleanup_calls.append(tick_number)

    monkeypatch.setattr("vibe3.runtime.heartbeat.append_orchestra_event", _capture)
    monkeypatch.setattr("vibe3.runtime.heartbeat.asyncio.sleep", _sleep_once)
    monkeypatch.setattr(server, "_run_periodic_check", _mock_cleanup)
    server._running = True

    await server._tick_loop()

    # Should trigger on tick #2 (2 % 2 == 0), not on #1 or #3
    assert 2 in cleanup_calls, f"Expected cleanup on tick #2, got: {cleanup_calls}"
    assert (
        1 not in cleanup_calls
    ), f"Should not cleanup on tick #1, got: {cleanup_calls}"
    assert (
        3 not in cleanup_calls
    ), f"Should not cleanup on tick #3, got: {cleanup_calls}"


@pytest.mark.asyncio
async def test_tick_loop_cleanup_failure_does_not_affect_services(monkeypatch) -> None:
    """Cleanup failure should not prevent service dispatch."""
    from vibe3.config.orchestra_config import PeriodicCheckConfig

    config = OrchestraConfig(
        polling_interval=1,
        max_concurrent_flows=3,
        periodic_check=PeriodicCheckConfig(interval_ticks=1),
    )
    server = HeartbeatServer(config)
    svc = _MockService()
    server.register(svc)

    events: list[str] = []

    def _capture(domain: str, message: str, **kwargs) -> None:
        events.append(f"{domain}:{message}")

    calls = {"count": 0}

    async def _sleep_once(_seconds: float) -> None:
        calls["count"] += 1
        if calls["count"] >= 2:
            server.stop()

    async def _mock_cleanup_failure(tick_number: int) -> None:
        raise RuntimeError("cleanup failed")

    monkeypatch.setattr("vibe3.runtime.heartbeat.append_orchestra_event", _capture)
    monkeypatch.setattr("vibe3.runtime.heartbeat.asyncio.sleep", _sleep_once)
    monkeypatch.setattr(server, "_run_periodic_check", _mock_cleanup_failure)
    server._running = True

    await server._tick_loop()

    # Service should still be ticked despite cleanup failure
    assert svc.ticks == 1, f"Expected 1 tick, got: {svc.ticks}"
    # Should have error event
    assert any(
        "cleanup failed" in item for item in events
    ), f"Expected cleanup error, got: {events}"


@pytest.mark.asyncio
async def test_tick_loop_skip_cleanup_when_disabled(monkeypatch) -> None:
    """Cleanup should not run when disabled in config."""
    from vibe3.config.orchestra_config import PeriodicCheckConfig

    config = OrchestraConfig(
        polling_interval=1,
        max_concurrent_flows=3,
        periodic_check=PeriodicCheckConfig(enabled=False),
    )
    server = HeartbeatServer(config)
    svc = _MockService()
    server.register(svc)

    cleanup_calls: list[int] = []

    tick_count = 0

    async def _sleep_once(_seconds: float) -> None:
        nonlocal tick_count
        tick_count += 1
        if tick_count >= 3:
            server.stop()

    async def _mock_cleanup(tick_number: int) -> None:
        cleanup_calls.append(tick_number)

    monkeypatch.setattr("vibe3.runtime.heartbeat.asyncio.sleep", _sleep_once)
    monkeypatch.setattr(server, "_run_periodic_check", _mock_cleanup)
    server._running = True

    await server._tick_loop()

    # Should not call cleanup when disabled
    assert (
        len(cleanup_calls) == 0
    ), f"Expected no cleanup calls when disabled, got: {cleanup_calls}"
