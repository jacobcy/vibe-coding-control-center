"""Tests for AssigneeDispatchService."""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.event_bus import GitHubEvent
from vibe3.orchestra.services.assignee_dispatch import AssigneeDispatchService


class _ImmediateLoop:
    async def run_in_executor(self, _executor, func, *args):  # type: ignore[no-untyped-def]
        return func(*args)


def _svc() -> AssigneeDispatchService:
    return AssigneeDispatchService(OrchestraConfig(polling_interval=900, dry_run=True))


def _assigned_event(
    issue_number: int = 42,
    assignee: str = "vibe-manager-agent",
) -> GitHubEvent:
    return GitHubEvent(
        event_type="issues",
        action="assigned",
        payload={
            "assignee": {"login": assignee},
            "issue": {
                "number": issue_number,
                "title": "test issue",
                "labels": [],
                "assignees": [{"login": assignee}],
            },
        },
        source="webhook",
    )


@pytest.mark.asyncio
async def test_handle_event_dispatches_when_assigned_to_manager() -> None:
    svc = _svc()
    svc._dep_checker = MagicMock()
    svc._dep_checker.check.return_value = (True, [])
    svc._dispatcher = MagicMock()
    svc._dispatcher.dispatch_manager.return_value = True
    svc._dispatcher.orchestrator.get_flow_for_issue.return_value = None

    with patch(
        "vibe3.orchestra.services.assignee_dispatch.asyncio.get_event_loop",
        return_value=_ImmediateLoop(),
    ):
        await svc.handle_event(_assigned_event())

    svc._dispatcher.dispatch_manager.assert_called_once()


@pytest.mark.asyncio
async def test_on_tick_cold_start_dispatches_assigned_issue_without_flow() -> None:
    svc = _svc()
    svc._github = MagicMock()
    svc._github.list_issues_with_assignees.return_value = [
        {
            "number": 42,
            "title": "test issue",
            "labels": [{"name": "priority/high"}],
            "assignees": [{"login": "vibe-manager-agent"}],
            "url": "https://example.com/issues/42",
        }
    ]
    svc._dep_checker = MagicMock()
    svc._dep_checker.check.return_value = (True, [])
    svc._dispatcher = MagicMock()
    svc._dispatcher.dispatch_manager.return_value = True
    svc._dispatcher.orchestrator.get_flow_for_issue.return_value = None

    with patch(
        "vibe3.orchestra.services.assignee_dispatch.asyncio.get_event_loop",
        return_value=_ImmediateLoop(),
    ):
        await svc.on_tick()

    svc._dispatcher.dispatch_manager.assert_called_once()


@pytest.mark.asyncio
async def test_on_tick_prunes_assignee_cache() -> None:
    """Assignee cache is pruned to only keep issues seen in current scan."""
    svc = _svc()
    svc._github = MagicMock()
    svc._github.list_issues_with_assignees.return_value = [
        {
            "number": 42,
            "title": "issue 42",
            "labels": [],
            "assignees": [{"login": "vibe-manager-agent"}],
            "url": "https://example.com/issues/42",
        },
        {
            "number": 43,
            "title": "issue 43",
            "labels": [],
            "assignees": [{"login": "alice"}],
            "url": "https://example.com/issues/43",
        },
    ]
    svc._dep_checker = MagicMock()
    svc._dep_checker.check.return_value = (True, [])
    svc._dispatcher = MagicMock()
    svc._dispatcher.dispatch_manager.return_value = True
    svc._dispatcher.orchestrator.get_flow_for_issue.return_value = None

    # Prepopulate cache with extra issue
    svc._assignee_cache = {
        42: frozenset(["vibe-manager-agent"]),
        43: frozenset(["alice"]),
        999: frozenset(["bob"]),  # Issue not in current scan
    }

    with patch(
        "vibe3.orchestra.services.assignee_dispatch.asyncio.get_event_loop",
        return_value=_ImmediateLoop(),
    ):
        await svc.on_tick()

    # Cache should be pruned to only issues seen in scan
    assert list(svc._assignee_cache.keys()) == [42, 43]
    assert 999 not in svc._assignee_cache
