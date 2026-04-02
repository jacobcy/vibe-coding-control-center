"""Tests for StateLabelDispatchService."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import MagicMock

import pytest

from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.services.state_label_dispatch import StateLabelDispatchService
from vibe3.runtime.event_bus import GitHubEvent


def _ready_issue_payload(labels: list[str] | None = None) -> dict[str, object]:
    issue_labels = labels or ["state/ready"]
    return {
        "number": 42,
        "title": "test issue",
        "labels": [{"name": name} for name in issue_labels],
        "assignees": [],
        "url": "https://example.com/issues/42",
    }


def _ready_event(
    label: str = "state/ready", issue_labels: list[str] | None = None
) -> GitHubEvent:
    return GitHubEvent(
        event_type="issues",
        action="labeled",
        payload={
            "label": {"name": label},
            "issue": _ready_issue_payload(issue_labels),
        },
        source="webhook",
    )


@pytest.fixture
def service() -> tuple[StateLabelDispatchService, MagicMock]:
    dispatcher = MagicMock()
    dispatcher.dispatch_manager.return_value = True
    dispatcher.orchestrator.get_flow_for_issue.return_value = None
    executor = ThreadPoolExecutor(max_workers=2)
    svc = StateLabelDispatchService(
        OrchestraConfig(dry_run=True, max_concurrent_flows=2),
        dispatcher=dispatcher,
        executor=executor,
    )
    try:
        yield svc, dispatcher
    finally:
        executor.shutdown(wait=True)


@pytest.mark.asyncio
async def test_handle_event_dispatches_on_state_ready_label(
    service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    svc, dispatcher = service

    await svc.handle_event(_ready_event())

    dispatcher.dispatch_manager.assert_called_once()


@pytest.mark.asyncio
async def test_handle_event_ignores_non_ready_label(
    service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    svc, dispatcher = service

    await svc.handle_event(_ready_event(label="state/blocked"))

    dispatcher.dispatch_manager.assert_not_called()


@pytest.mark.asyncio
async def test_on_tick_skips_issue_already_in_progress(
    service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    svc, dispatcher = service
    svc._list_ready_issues = MagicMock(
        return_value=[_ready_issue_payload(["state/ready", "state/in-progress"])]
    )

    await svc.on_tick()

    dispatcher.dispatch_manager.assert_not_called()


@pytest.mark.asyncio
async def test_webhook_and_polling_overlap_dispatch_only_once(
    service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    svc, dispatcher = service
    started = Event()
    release = Event()

    def blocking_dispatch(_issue):
        started.set()
        if not release.wait(timeout=1):
            raise AssertionError("dispatch did not finish in time")
        return True

    dispatcher.dispatch_manager.side_effect = blocking_dispatch
    svc._list_ready_issues = MagicMock(return_value=[_ready_issue_payload()])

    webhook_task = asyncio.create_task(svc.handle_event(_ready_event()))
    assert await asyncio.to_thread(started.wait, 1)

    polling_task = asyncio.create_task(svc.on_tick())
    release.set()
    await asyncio.gather(webhook_task, polling_task)

    assert dispatcher.dispatch_manager.call_count == 1
