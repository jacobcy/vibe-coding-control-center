"""Tests for StateLabelDispatchService core dispatch logic."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock

import pytest

from vibe3.models.orchestration import IssueState
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.services.state_label_dispatch import StateLabelDispatchService
from vibe3.runtime.event_bus import GitHubEvent


def _issue_payload(
    number: int = 42, labels: list[str] | None = None
) -> dict[str, object]:
    issue_labels = labels or ["state/claimed"]
    return {
        "number": number,
        "title": "test issue",
        "labels": [{"name": name} for name in issue_labels],
        "assignees": [],
        "url": f"https://example.com/issues/{number}",
    }


def _event() -> GitHubEvent:
    return GitHubEvent(
        event_type="issues",
        action="labeled",
        payload={"issue": _issue_payload()},
        source="webhook",
    )


@pytest.fixture
def service() -> Generator[tuple[StateLabelDispatchService, MagicMock], None, None]:
    manager = MagicMock()
    manager.flow_manager.get_flow_for_issue.return_value = {"branch": "task/issue-42"}
    executor = ThreadPoolExecutor(max_workers=2)
    svc = StateLabelDispatchService(
        OrchestraConfig(dry_run=True, max_concurrent_flows=2),
        trigger_state=IssueState.CLAIMED,
        trigger_name="plan",
        manager=manager,
        executor=executor,
    )
    svc._store = MagicMock()
    svc._store.get_flow_state.return_value = {"latest_actor": "agent:test"}
    svc._backend = MagicMock()
    svc._backend.start_async_command.return_value = MagicMock(
        tmux_session="vibe3-plan-issue-42",
        log_path=Path("/tmp/vibe3-plan-issue-42.log"),
    )
    svc._has_live_dispatch = MagicMock(return_value=False)
    try:
        yield svc, manager
    finally:
        executor.shutdown(wait=True)


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


@pytest.mark.asyncio
async def test_handle_event_is_noop(
    service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    svc, manager = service

    await svc.handle_event(_event())

    manager.flow_manager.get_flow_for_issue.assert_not_called()


@pytest.mark.asyncio
async def test_on_tick_dispatches_matching_state(
    service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    svc, _ = service
    svc._github = MagicMock()
    svc._github.view_issue.return_value = {"number": 42, "comments": []}
    svc._github.list_issues.return_value = [_issue_payload(labels=["state/claimed"])]

    await svc.on_tick()

    svc._backend.start_async_command.assert_called_once()
    svc._store.update_flow_state.assert_called_once()
    assert "planner_session_id" not in svc._store.update_flow_state.call_args.kwargs


@pytest.mark.asyncio
async def test_on_tick_skips_when_plan_ref_already_exists(
    service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    svc, _ = service
    svc._github = MagicMock()
    svc._github.view_issue.return_value = {"number": 42, "comments": []}
    svc._github.list_issues.return_value = [_issue_payload(labels=["state/claimed"])]
    svc._store.get_flow_state.return_value = {"plan_ref": "/tmp/plan.md"}

    await svc.on_tick()

    svc._backend.start_async_command.assert_not_called()


@pytest.mark.asyncio
async def test_on_tick_skips_noncanonical_manual_flow_for_plan(
    service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    svc, manager = service
    svc._github = MagicMock()
    svc._github.view_issue.return_value = {"number": 42, "comments": []}
    svc._github.list_issues.return_value = [_issue_payload(labels=["state/claimed"])]
    manager.flow_manager.get_flow_for_issue.return_value = {"branch": "dev/issue-435"}

    await svc.on_tick()

    svc._backend.start_async_command.assert_not_called()


@pytest.mark.asyncio
async def test_on_tick_dispatches_manager_for_ready_issue(
    manager_service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    svc, manager = manager_service
    svc._github.list_issues.return_value = [_issue_payload(labels=["state/ready"])]

    await svc.on_tick()

    manager.dispatch_manager.assert_called_once()


@pytest.mark.asyncio
async def test_on_tick_skips_when_live_tmux_session_exists(
    service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    svc, _ = service
    svc._github = MagicMock()
    svc._github.view_issue.return_value = {"number": 42, "comments": []}
    svc._github.list_issues.return_value = [_issue_payload(labels=["state/claimed"])]
    svc._has_live_dispatch.return_value = True

    await svc.on_tick()

    svc._backend.start_async_command.assert_not_called()


@pytest.mark.asyncio
async def test_on_tick_does_not_dispatch_when_issue_already_in_flight(
    manager_service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    """Issue already in _in_flight_dispatches should not be dispatched again."""
    svc, manager = manager_service
    svc._github.list_issues.return_value = [_issue_payload(labels=["state/ready"])]
    # Simulate issue already in-flight with live session
    svc._in_flight_dispatches.add(42)
    svc._has_live_dispatch = MagicMock(return_value=True)
    manager.flow_manager.get_flow_for_issue.return_value = {"branch": "task/issue-42"}

    await svc.on_tick()

    # Should not dispatch again because already in-flight
    manager.dispatch_manager.assert_not_called()


@pytest.mark.asyncio
async def test_on_tick_does_not_dispatch_when_live_dispatch_exists(
    service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    """Issue with live dispatch should not be dispatched again."""
    svc, _ = service
    svc._github = MagicMock()
    svc._github.view_issue.return_value = {"number": 42, "comments": []}
    svc._github.list_issues.return_value = [_issue_payload(labels=["state/claimed"])]
    # Simulate live dispatch exists
    svc._has_live_dispatch.return_value = True

    await svc.on_tick()

    # Should not dispatch because live session exists
    svc._backend.start_async_command.assert_not_called()
