"""Tests for HeartbeatServer."""

from pathlib import Path

import pytest

from vibe3.orchestra.config import OrchestraConfig
from vibe3.runtime.event_bus import GitHubEvent, ServiceBase
from vibe3.runtime.heartbeat import HeartbeatServer


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


def test_run_separator_writes_header(tmp_path: Path) -> None:
    import os

    from vibe3.orchestra.logging import append_orchestra_run_separator

    os.environ["VIBE3_ORCHESTRA_EVENT_LOG"] = "1"
    log_path = tmp_path / "temp" / "logs" / "orchestra" / "events.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("old event\n", encoding="utf-8")
    append_orchestra_run_separator(repo_root=tmp_path, title="server run start")
    text = log_path.read_text()
    assert "old event" not in text
    assert "========== server run start @" in text


@pytest.mark.asyncio
async def test_tick_loop_logs_start_and_completion(monkeypatch) -> None:
    server = HeartbeatServer(
        OrchestraConfig(polling_interval=1, max_concurrent_flows=3)
    )
    svc = _MockService()
    server.register(svc)

    events: list[str] = []

    def _capture(domain: str, message: str) -> None:
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

    assert any("server:heartbeat tick #1 start" == item for item in events)
    assert any(
        f"server:heartbeat tick #1 services: {svc.service_name}" == item
        for item in events
    )
    assert any("server:heartbeat tick #1 completed in " in item for item in events)
