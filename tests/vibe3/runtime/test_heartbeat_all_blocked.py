"""Test heartbeat stops when all non-close issues are blocked."""

from unittest.mock import MagicMock

import pytest

from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.orchestra.failed_gate import GateResult
from vibe3.runtime.heartbeat import HeartbeatServer


@pytest.mark.asyncio
async def test_heartbeat_sets_all_blocked_gate(monkeypatch):
    """When all collected issues are blocked, should set all_blocked gate."""
    config = OrchestraConfig(polling_interval=1, max_concurrent_flows=3)
    server = HeartbeatServer(config)

    # Mock failed gate
    gate = MagicMock()
    gate.check.return_value = GateResult.open_gate()
    gate.activate = MagicMock()
    server._failed_gate = gate

    # Mock coordinator that reports all blocked
    coordinator = MagicMock()
    coordinator.get_all_blocked_status = MagicMock(return_value=True)
    server._coordinator = coordinator

    # Track events
    events: list[str] = []

    def _capture(domain: str, message: str, **kwargs) -> None:
        events.append(f"{domain}:{message}")

    # Mock sleep as safety net (all_blocked should stop heartbeat before 3rd call)
    calls = {"count": 0}

    async def _sleep_once(_seconds: float) -> None:
        calls["count"] += 1
        if calls["count"] >= 3:
            server.stop()

    # Mock ErrorTrackingService (cleanup logic uses it)
    cleanup_service = MagicMock()
    cleanup_service.cleanup_old_errors.return_value = 0
    cleanup_service.cleanup_terminal_issue_errors.return_value = 0

    from vibe3.runtime import heartbeat

    monkeypatch.setattr("vibe3.runtime.heartbeat.append_orchestra_event", _capture)
    monkeypatch.setattr("vibe3.runtime.heartbeat.asyncio.sleep", _sleep_once)
    monkeypatch.setattr(
        heartbeat.ErrorTrackingService,
        "get_instance",
        staticmethod(lambda: cleanup_service),
    )
    server._running = True

    await server._tick_loop()

    # Should have activated "all_blocked" gate
    gate.activate.assert_called_once_with(
        reason="all non-close issues are blocked",
        error_code="ALL_BLOCKED",
    )

    # Should have stopped heartbeat
    assert server._running is False

    # Should have logged the stop
    assert any("all issues blocked" in item for item in events)


@pytest.mark.asyncio
async def test_heartbeat_continues_when_not_all_blocked(monkeypatch):
    """When not all issues are blocked, heartbeat should continue normally."""
    config = OrchestraConfig(polling_interval=1, max_concurrent_flows=3)
    server = HeartbeatServer(config)

    # Mock service to track ticks
    class _MockService:
        service_name = "MockService"
        is_dispatch_service = False
        ticks = 0

        async def on_tick(self, tick_id: int = 0) -> None:
            self.ticks += 1

    svc = _MockService()
    server.register(svc)

    # Mock failed gate (open)
    gate = MagicMock()
    gate.check.return_value = GateResult.open_gate()
    server._failed_gate = gate

    # Mock coordinator that reports NOT all blocked
    coordinator = MagicMock()
    coordinator.get_all_blocked_status = MagicMock(return_value=False)
    server._coordinator = coordinator

    # Mock ErrorTrackingService
    cleanup_service = MagicMock()
    cleanup_service.cleanup_old_errors.return_value = 0
    cleanup_service.cleanup_terminal_issue_errors.return_value = 0

    from vibe3.runtime import heartbeat

    # Mock sleep to stop after 2 ticks
    calls = {"count": 0}

    async def _sleep_once(_seconds: float) -> None:
        calls["count"] += 1
        if calls["count"] >= 2:
            server.stop()

    monkeypatch.setattr("vibe3.runtime.heartbeat.asyncio.sleep", _sleep_once)
    monkeypatch.setattr(
        heartbeat.ErrorTrackingService,
        "get_instance",
        staticmethod(lambda: cleanup_service),
    )
    server._running = True

    await server._tick_loop()

    # Should NOT have activated gate
    gate.activate.assert_not_called()

    # Service should have been ticked
    assert svc.ticks >= 1


@pytest.mark.asyncio
async def test_heartbeat_handles_missing_coordinator_gracefully(monkeypatch):
    """When coordinator is not set, heartbeat should continue normally."""
    config = OrchestraConfig(polling_interval=1, max_concurrent_flows=3)
    server = HeartbeatServer(config)

    # Mock service to track ticks
    class _MockService:
        service_name = "MockService"
        is_dispatch_service = False
        ticks = 0

        async def on_tick(self, tick_id: int = 0) -> None:
            self.ticks += 1

    svc = _MockService()
    server.register(svc)

    # Mock failed gate (open)
    gate = MagicMock()
    gate.check.return_value = GateResult.open_gate()
    server._failed_gate = gate

    # No coordinator set (None)
    assert not hasattr(server, "_coordinator") or server._coordinator is None

    # Mock ErrorTrackingService
    cleanup_service = MagicMock()
    cleanup_service.cleanup_old_errors.return_value = 0
    cleanup_service.cleanup_terminal_issue_errors.return_value = 0

    from vibe3.runtime import heartbeat

    # Mock sleep to stop after 2 ticks
    calls = {"count": 0}

    async def _sleep_once(_seconds: float) -> None:
        calls["count"] += 1
        if calls["count"] >= 2:
            server.stop()

    monkeypatch.setattr("vibe3.runtime.heartbeat.asyncio.sleep", _sleep_once)
    monkeypatch.setattr(
        heartbeat.ErrorTrackingService,
        "get_instance",
        staticmethod(lambda: cleanup_service),
    )
    server._running = True

    await server._tick_loop()

    # Should NOT have activated gate
    gate.activate.assert_not_called()

    # Service should have been ticked
    assert svc.ticks >= 1


@pytest.mark.asyncio
async def test_heartbeat_no_stop_when_queue_empty(monkeypatch):
    """When frozen queue is empty, heartbeat should continue (not all_blocked)."""
    config = OrchestraConfig(polling_interval=1, max_concurrent_flows=3)
    server = HeartbeatServer(config)

    # Mock service to track ticks
    class _MockService:
        service_name = "MockService"
        is_dispatch_service = False
        ticks = 0

        async def on_tick(self, tick_id: int = 0) -> None:
            self.ticks += 1

    svc = _MockService()
    server.register(svc)

    # Mock failed gate (open)
    gate = MagicMock()
    gate.check.return_value = GateResult.open_gate()
    server._failed_gate = gate

    # Mock coordinator with empty queue (get_all_blocked_status returns False)
    coordinator = MagicMock()
    coordinator.get_all_blocked_status = MagicMock(return_value=False)
    server._coordinator = coordinator

    # Mock ErrorTrackingService
    cleanup_service = MagicMock()
    cleanup_service.cleanup_old_errors.return_value = 0
    cleanup_service.cleanup_terminal_issue_errors.return_value = 0

    from vibe3.runtime import heartbeat

    # Mock sleep to stop after 2 ticks
    calls = {"count": 0}

    async def _sleep_once(_seconds: float) -> None:
        calls["count"] += 1
        if calls["count"] >= 2:
            server.stop()

    monkeypatch.setattr("vibe3.runtime.heartbeat.asyncio.sleep", _sleep_once)
    monkeypatch.setattr(
        heartbeat.ErrorTrackingService,
        "get_instance",
        staticmethod(lambda: cleanup_service),
    )
    server._running = True

    await server._tick_loop()

    # Should NOT have activated gate
    gate.activate.assert_not_called()

    # Service should have been ticked
    assert svc.ticks >= 1
