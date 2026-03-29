"""Tests for HeartbeatServer."""

import pytest

from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.event_bus import GitHubEvent, ServiceBase
from vibe3.orchestra.heartbeat import HeartbeatServer


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
