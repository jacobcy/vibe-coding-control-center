"""Tests for StateLabelDispatchService capacity management."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Generator
from unittest.mock import MagicMock

import pytest

from vibe3.models.orchestration import IssueState
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.services.state_label_dispatch import StateLabelDispatchService


def _issue_payload(
    number: int = 42, labels: list[str] | None = None
) -> dict[str, object]:
    issue_labels = labels or ["state/ready"]
    return {
        "number": number,
        "title": "test issue",
        "labels": [{"name": name} for name in issue_labels],
        "assignees": [],
        "url": f"https://example.com/issues/{number}",
    }


@pytest.fixture
def manager_service() -> (
    Generator[tuple[StateLabelDispatchService, MagicMock], None, None]
):
    manager = MagicMock()
    executor = ThreadPoolExecutor(max_workers=2)
    svc = StateLabelDispatchService(
        OrchestraConfig(dry_run=True, max_concurrent_flows=2),
        trigger_state=IssueState.READY,
        trigger_name="manager",
        manager=manager,
        executor=executor,
    )
    svc._github = MagicMock()
    svc._github.view_issue.return_value = {"number": 42, "comments": []}
    svc._github.view_issue.return_value = {"number": 42, "comments": []}
    svc._store = MagicMock()
    try:
        yield svc, manager
    finally:
        executor.shutdown(wait=True)


# === Manager capacity limit tests ===


@pytest.mark.asyncio
async def test_manager_tick_dispatches_at_most_remaining_capacity(
    manager_service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    """Manager tick should respect remaining capacity and not over-dispatch."""
    svc, manager = manager_service
    # Set up 6 ready issues but max_concurrent_flows=2 (from fixture)
    # No active flows currently
    ready_issues = [
        _issue_payload(number=i, labels=["state/ready"])
        for i in [410, 417, 418, 419, 431, 436]
    ]
    svc._github.list_issues.return_value = ready_issues
    svc._has_live_dispatch = MagicMock(return_value=False)
    # No active flows and no in-flight dispatches
    manager.flow_manager.get_flow_for_issue.return_value = {"branch": "task/issue-410"}

    await svc.on_tick()

    # Should dispatch at most 2 (max_concurrent_flows) issues in this tick
    # Not all 6 ready issues
    assert manager.dispatch_manager.call_count <= 2
    # Verify that we dispatched at least one (capacity not zero)
    assert manager.dispatch_manager.call_count >= 1


@pytest.mark.asyncio
async def test_manager_tick_logs_throttled_issue_numbers_when_capacity_exhausted(
    manager_service: tuple[StateLabelDispatchService, MagicMock],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Throttled issues should be logged with their issue numbers."""

    from loguru import logger

    # Set up loguru to propagate to standard logging for caplog
    handler_id = logger.add(
        caplog.handler,  # Use pytest's caplog handler
        format="{message}",
        level="INFO",
    )

    try:
        svc, manager = manager_service
        # Set up 6 ready issues but max_concurrent_flows=2
        ready_issues = [
            _issue_payload(number=i, labels=["state/ready"])
            for i in [410, 417, 418, 419, 431, 436]
        ]
        svc._github.list_issues.return_value = ready_issues
        svc._has_live_dispatch = MagicMock(return_value=False)
        manager.flow_manager.get_flow_for_issue.return_value = {
            "branch": "task/issue-410"
        }

        await svc.on_tick()

        # Should log throttled issues
        # At least some issues should be throttled (capacity < ready count)
        log_messages = [record.message for record in caplog.records]
        # Look for evidence of throttling in logs
        assert any(
            "throttle" in msg.lower() or "capacity" in msg.lower()
            for msg in log_messages
        ), f"Expected throttle log, got: {log_messages}"
    finally:
        logger.remove(handler_id)


# === Tick logging detail tests ===


@pytest.mark.asyncio
async def test_manager_tick_logs_selected_dispatched_and_throttled_issues(
    manager_service: tuple[StateLabelDispatchService, MagicMock],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Manager tick should log which issues were selected, dispatched, and throttled."""
    from loguru import logger

    handler_id = logger.add(caplog.handler, format="{message}", level="INFO")

    try:
        svc, manager = manager_service
        # Set up 6 ready issues but max_concurrent_flows=2
        ready_issues = [
            _issue_payload(number=i, labels=["state/ready"])
            for i in [410, 417, 418, 419, 431, 436]
        ]
        svc._github.list_issues.return_value = ready_issues
        svc._has_live_dispatch = MagicMock(return_value=False)
        manager.flow_manager.get_flow_for_issue.return_value = {
            "branch": "task/issue-410"
        }

        await svc.on_tick()

        log_messages = [record.message for record in caplog.records]
        # Should log selected issues
        assert any(
            "410" in msg and "417" in msg for msg in log_messages
        ), f"Expected selected issues log, got: {log_messages}"
        # Should log throttled issues
        assert any(
            "418" in msg or "419" in msg or "431" in msg or "436" in msg
            for msg in log_messages
        ), f"Expected throttled issues log, got: {log_messages}"
    finally:
        logger.remove(handler_id)
