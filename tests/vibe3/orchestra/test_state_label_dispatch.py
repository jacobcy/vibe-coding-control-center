"""Tests for StateLabelDispatchService."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
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
        manager=dispatcher,
        executor=executor,
    )
    try:
        yield svc, dispatcher
    finally:
        executor.shutdown(wait=True)


@pytest.mark.asyncio
async def test_handle_event_observed_state_ready_label(
    service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    """StateLabelDispatch is now mirror-only and should NOT trigger dispatch."""
    svc, dispatcher = service

    await svc.handle_event(_ready_event())

    # Should not dispatch anymore
    dispatcher.dispatch_manager.assert_not_called()


@pytest.mark.asyncio
async def test_handle_event_ignores_non_ready_label(
    service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    svc, dispatcher = service

    await svc.handle_event(_ready_event(label="state/blocked"))

    dispatcher.dispatch_manager.assert_not_called()


@pytest.mark.asyncio
async def test_on_tick_is_no_op(
    service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    """on_tick is now a no-op in mirror-only mode."""
    svc, dispatcher = service
    svc._list_ready_issues = MagicMock(
        return_value=[_ready_issue_payload(["state/ready"])]
    )

    await svc.on_tick()

    dispatcher.dispatch_manager.assert_not_called()
