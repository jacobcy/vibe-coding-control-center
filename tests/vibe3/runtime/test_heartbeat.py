"""Tests for HeartbeatServer."""

from pathlib import Path

import pytest

from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.runtime.heartbeat import HeartbeatServer
from vibe3.runtime.service_protocol import GitHubEvent, ServiceBase


def _config() -> OrchestraConfig:
    return OrchestraConfig(polling_interval=900, max_concurrent_flows=3)


class _MockService(ServiceBase):
    event_types = ["issues"]

    def __init__(self) -> None:
        self.events: list[GitHubEvent] = []
        self.ticks: int = 0

    async def handle_event(self, event: GitHubEvent) -> None:
        self.events.append(event)

    async def on_tick(self) -> None:
        self.ticks += 1


def test_register_service() -> None:
    server = HeartbeatServer(_config())
    svc = _MockService()
    server.register(svc)
    assert svc in server._services
    assert "MockService" in server.service_names[0]


@pytest.mark.asyncio
async def test_emit_dispatches_to_matching_service() -> None:
    server = HeartbeatServer(_config())
    svc = _MockService()
    server.register(svc)

    event = GitHubEvent(
        event_type="issues", action="assigned", payload={}, source="webhook"
    )
    await server.emit(event)

    # Drain the queue via _dispatch_event directly
    queued = await server._event_queue.get()
    await server._dispatch_event(queued)

    assert len(svc.events) == 1
    assert svc.events[0].action == "assigned"


@pytest.mark.asyncio
async def test_no_dispatch_for_unmatched_event_type() -> None:
    server = HeartbeatServer(_config())
    svc = _MockService()  # only handles "issues"
    server.register(svc)

    event = GitHubEvent(event_type="push", action="push", payload={}, source="webhook")
    await server.emit(event)
    queued = await server._event_queue.get()
    await server._dispatch_event(queued)

    assert svc.events == []


@pytest.mark.asyncio
async def test_tick_calls_on_tick_for_all_services() -> None:
    server = HeartbeatServer(_config())
    svc1 = _MockService()
    svc2 = _MockService()
    server.register(svc1)
    server.register(svc2)

    await server._tick_service(svc1)
    await server._tick_service(svc2)

    assert svc1.ticks == 1
    assert svc2.ticks == 1


def test_run_separator_appends_instead_of_truncating(
    tmp_path: Path, monkeypatch
) -> None:
    """Run separator should append to existing events.log, not overwrite it."""
    import os

    from vibe3.orchestra.logging import append_orchestra_run_separator

    # Clear any environment variables that might affect log directory
    monkeypatch.delenv("VIBE3_ASYNC_LOG_DIR", raising=False)

    os.environ["VIBE3_ORCHESTRA_EVENT_LOG"] = "1"
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

    mock_gate = type("_Gate", (), {"check": lambda self: None})()
    server._failed_gate = mock_gate

    monkeypatch.setattr("vibe3.runtime.heartbeat.append_orchestra_event", _capture)
    monkeypatch.setattr("vibe3.runtime.heartbeat.asyncio.sleep", _sleep_once)
    server._running = True

    await server._tick_loop()

    assert svc.ticks == 1
    assert any("server:tick #1 start" == item for item in events)


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
