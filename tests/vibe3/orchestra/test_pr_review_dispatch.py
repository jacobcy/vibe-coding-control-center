"""Tests for PRReviewDispatchService."""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.event_bus import GitHubEvent
from vibe3.orchestra.services.pr_review_dispatch import PRReviewDispatchService


class _ImmediateLoop:
    async def run_in_executor(self, _executor, func, *args):  # type: ignore[no-untyped-def]
        return func(*args)


def _svc() -> PRReviewDispatchService:
    return PRReviewDispatchService(OrchestraConfig(polling_interval=900, dry_run=True))


def _pr_event(
    action: str,
    requested_reviewer: str | None = None,
    requested_reviewers: list[str] | None = None,
    pr_number: int = 347,
) -> GitHubEvent:
    payload = {
        "number": pr_number,
        "pull_request": {
            "title": "test pr",
            "requested_reviewers": [
                {"login": login} for login in (requested_reviewers or [])
            ],
        },
    }
    if requested_reviewer is not None:
        payload["requested_reviewer"] = {"login": requested_reviewer}
    return GitHubEvent(
        event_type="pull_request",
        action=action,
        payload=payload,
        source="webhook",
    )


@pytest.mark.asyncio
async def test_review_requested_dispatches_for_manager_reviewer() -> None:
    svc = _svc()
    svc._dispatcher = MagicMock()
    svc._dispatcher.dispatch_pr_review.return_value = True

    with patch(
        "vibe3.orchestra.services.pr_review_dispatch.asyncio.get_event_loop",
        return_value=_ImmediateLoop(),
    ):
        await svc.handle_event(
            _pr_event("review_requested", requested_reviewer="vibe-manager-agent")
        )

    svc._dispatcher.dispatch_pr_review.assert_called_once_with(347)


@pytest.mark.asyncio
async def test_review_requested_ignores_non_manager_reviewer() -> None:
    svc = _svc()
    svc._dispatcher = MagicMock()

    with patch(
        "vibe3.orchestra.services.pr_review_dispatch.asyncio.get_event_loop",
        return_value=_ImmediateLoop(),
    ):
        await svc.handle_event(
            _pr_event("review_requested", requested_reviewer="someone-else")
        )

    svc._dispatcher.dispatch_pr_review.assert_not_called()


@pytest.mark.asyncio
async def test_ready_for_review_dispatches_when_manager_requested() -> None:
    svc = _svc()
    svc._dispatcher = MagicMock()
    svc._dispatcher.dispatch_pr_review.return_value = True

    with patch(
        "vibe3.orchestra.services.pr_review_dispatch.asyncio.get_event_loop",
        return_value=_ImmediateLoop(),
    ):
        await svc.handle_event(
            _pr_event(
                "ready_for_review",
                requested_reviewers=["vibe-manager-agent", "teammate"],
            )
        )

    svc._dispatcher.dispatch_pr_review.assert_called_once_with(347)


@pytest.mark.asyncio
async def test_review_requested_dispatches_when_manager_in_requested_reviewers() -> (
    None
):
    svc = _svc()
    svc._dispatcher = MagicMock()
    svc._dispatcher.dispatch_pr_review.return_value = True

    with patch(
        "vibe3.orchestra.services.pr_review_dispatch.asyncio.get_event_loop",
        return_value=_ImmediateLoop(),
    ):
        await svc.handle_event(
            _pr_event(
                "review_requested",
                requested_reviewer=None,
                requested_reviewers=["vibe-manager-agent"],
            )
        )

    svc._dispatcher.dispatch_pr_review.assert_called_once_with(347)
