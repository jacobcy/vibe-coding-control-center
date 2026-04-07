"""Tests for StateLabelDispatchService core dispatch logic."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

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
async def test_on_tick_appends_dispatcher_events(
    service: tuple[StateLabelDispatchService, MagicMock],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    svc, _ = service
    svc._github = MagicMock()
    svc._github.view_issue.return_value = {"number": 42, "comments": []}
    svc._github.list_issues.return_value = [_issue_payload(labels=["state/claimed"])]
    events: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "vibe3.orchestra.services.state_label_dispatch.append_orchestra_event",
        lambda component, message, repo_root=None: events.append((component, message)),
    )

    await svc.on_tick()

    assert any("tick ready issues" in message for _, message in events)
    assert any("dispatching #42" in message for _, message in events)


@pytest.mark.asyncio
async def test_on_tick_skips_plan_when_live_execution_status_running(
    service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    svc, _ = service
    svc._github = MagicMock()
    svc._github.view_issue.return_value = {"number": 42, "comments": []}
    svc._github.list_issues.return_value = [_issue_payload(labels=["state/claimed"])]
    svc._store.get_flow_state.return_value = {
        "planner_status": "running",
        "planner_session_id": None,
        "plan_ref": None,
    }
    svc._has_live_dispatch.return_value = True

    await svc.on_tick()

    svc._backend.start_async_command.assert_not_called()


@pytest.mark.asyncio
async def test_on_tick_dispatches_plan_when_running_status_is_stale(
    service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    svc, _ = service
    svc._github = MagicMock()
    svc._github.view_issue.return_value = {"number": 42, "comments": []}
    svc._github.list_issues.return_value = [_issue_payload(labels=["state/claimed"])]
    svc._store.get_flow_state.return_value = {
        "planner_status": "running",
        "planner_session_id": None,
        "plan_ref": None,
    }
    svc._has_live_dispatch.return_value = False

    await svc.on_tick()

    svc._backend.start_async_command.assert_called_once()


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
async def test_on_tick_dispatches_manager_for_handoff_issue(
    manager_service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    svc, manager = manager_service
    svc.trigger_state = IssueState.HANDOFF
    svc._github.list_issues.return_value = [_issue_payload(labels=["state/handoff"])]
    manager.flow_manager.get_flow_for_issue.return_value = {"branch": "task/issue-42"}
    svc._store.get_flow_state.return_value = {"manager_session_id": None}

    await svc.on_tick()

    manager.dispatch_manager.assert_called_once()


@pytest.mark.asyncio
async def test_on_tick_appends_manager_started_event(
    manager_service: tuple[StateLabelDispatchService, MagicMock],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    svc, manager = manager_service
    svc._github.list_issues.return_value = [_issue_payload(labels=["state/ready"])]
    manager.dispatch_manager.return_value = True
    events: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "vibe3.orchestra.services.state_label_dispatch.append_orchestra_event",
        lambda component, message, repo_root=None: events.append((component, message)),
    )

    await svc.on_tick()

    assert any("dispatching #42" in message for _, message in events)
    assert any("started #42" in message for _, message in events)


@pytest.mark.asyncio
async def test_on_tick_appends_manager_rejected_event_when_dispatch_fails(
    manager_service: tuple[StateLabelDispatchService, MagicMock],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    svc, manager = manager_service
    svc._github.list_issues.return_value = [_issue_payload(labels=["state/ready"])]
    manager.dispatch_manager.return_value = False
    manager.queued_issues = {42}
    events: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "vibe3.orchestra.services.state_label_dispatch.append_orchestra_event",
        lambda component, message, repo_root=None: events.append((component, message)),
    )

    await svc.on_tick()

    assert any("dispatching #42" in message for _, message in events)
    assert any("deferred #42" in message.lower() for _, message in events)


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


def test_resolve_cwd_uses_manager_repo_path_in_debug(
    service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    svc, manager = service
    svc.config = OrchestraConfig(debug=True)
    manager.repo_path = Path("/debug-wt")

    with patch(
        "vibe3.orchestra.services.state_label_dispatch.WorktreeManager"
    ) as mock_worktree_manager:
        mock_instance = MagicMock()
        mock_instance.resolve_manager_cwd.return_value = (
            Path("/debug-wt/.worktrees/issue-42"),
            False,
        )
        mock_worktree_manager.return_value = mock_instance

        resolved = svc._resolve_cwd(42, "task/issue-42")

    assert resolved == Path("/debug-wt/.worktrees/issue-42")
    mock_worktree_manager.assert_called_once_with(svc.config, Path("/debug-wt"))


def test_build_command_uses_baseline_project_root(
    service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    svc, _ = service

    command = svc._build_command(42)

    assert command[:3] == ["uv", "run", "--project"]
    assert command[4:7] == ["python", "-I", command[6]]
    assert command[5] == "-I"
    assert command[6].endswith("/src/vibe3/cli.py")


@pytest.mark.asyncio
async def test_manager_dispatch_respects_queue_ordering(
    manager_service: tuple[StateLabelDispatchService, MagicMock],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that manager dispatches ready issues in queue order."""
    svc, manager = manager_service

    # Create issues with different queue metadata
    # Issue 100: v0.3, roadmap/p1, priority/7 (should be 4th)
    # Issue 200: v0.3, roadmap/p0, priority/7 (should be 3rd)
    # Issue 300: v0.1, roadmap/p1, priority/5 (should be 2nd)
    # Issue 400: v0.1, roadmap/p0, priority/9 (should be 1st)
    raw_issues = [
        {
            "number": 100,
            "title": "A",
            "labels": [
                {"name": "state/ready"},
                {"name": "roadmap/p1"},
                {"name": "priority/7"},
            ],
            "assignees": [],
            "milestone": {"title": "v0.3", "number": 3},
        },
        {
            "number": 200,
            "title": "B",
            "labels": [
                {"name": "state/ready"},
                {"name": "roadmap/p0"},
                {"name": "priority/7"},
            ],
            "assignees": [],
            "milestone": {"title": "v0.3", "number": 3},
        },
        {
            "number": 300,
            "title": "C",
            "labels": [
                {"name": "state/ready"},
                {"name": "roadmap/p1"},
                {"name": "priority/5"},
            ],
            "assignees": [],
            "milestone": {"title": "v0.1", "number": 1},
        },
        {
            "number": 400,
            "title": "D",
            "labels": [
                {"name": "state/ready"},
                {"name": "roadmap/p0"},
                {"name": "priority/9"},
            ],
            "assignees": [],
            "milestone": {"title": "v0.1", "number": 1},
        },
    ]

    svc._github.list_issues.return_value = raw_issues
    manager.dispatch_manager.return_value = True

    events: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "vibe3.orchestra.services.state_label_dispatch.append_orchestra_event",
        lambda component, message, repo_root=None: events.append((component, message)),
    )

    await svc.on_tick()

    # Verify manager.dispatch_manager was called in queue order
    # Capacity=2, so should dispatch 2 highest priority issues
    assert manager.dispatch_manager.call_count == 2

    # Get the issue numbers from dispatch calls
    # dispatch_manager receives IssueInfo objects
    first_call_issue = manager.dispatch_manager.call_args_list[0][0][0]
    second_call_issue = manager.dispatch_manager.call_args_list[1][0][0]

    # Should dispatch in queue order: #400 first, #300 second
    assert first_call_issue.number == 400
    assert second_call_issue.number == 300

    # Verify event log shows ready queue in correct order
    tick_events = [msg for _, msg in events if "tick ready issues" in msg]
    assert len(tick_events) == 1
    # Ready queue should list issues in order: 400, 300, 200, 100
    ready_queue_msg = tick_events[0]
    assert "#400" in ready_queue_msg
    # The message should show all ready issues in sorted order
    # Format: "tick ready issues: #400, #300, #200, #100"
    assert ready_queue_msg.index("#400") < ready_queue_msg.index("#300")
    assert ready_queue_msg.index("#300") < ready_queue_msg.index("#200")
    assert ready_queue_msg.index("#200") < ready_queue_msg.index("#100")
