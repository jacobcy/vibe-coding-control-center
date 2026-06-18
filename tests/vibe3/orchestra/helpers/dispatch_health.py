"""Shared helpers for dispatch health check tests.

Extracted from test_dispatch_health_checks.py to reduce per-test boilerplate.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from vibe3.models import CheckResult
from vibe3.models.orchestration import IssueInfo, IssueState


def make_health_coordinator(
    *,
    flow_context_branch: str = "task/issue-42",
    store_flow_state: dict | None = None,
    check_result: CheckResult | None = None,
) -> tuple:
    """Create a coordinator with mocked deps for _check_dispatch_health tests.

    Returns (coordinator, mocks) where mocks exposes named mock objects
    for assertion (flow_blocker, store, check_service).
    """
    from vibe3.orchestra.global_dispatch_coordinator import (
        GlobalDispatchCoordinator,
    )

    config = MagicMock()
    config.max_concurrent_flows = 10
    config.repo = "owner/repo"
    config.supervisor_handoff = MagicMock()
    config.supervisor_handoff.issue_label = "supervisor"

    capacity = MagicMock()
    github = MagicMock()
    store = MagicMock()
    store.db_path = ":memory:"
    store.get_flow_state.return_value = store_flow_state

    flow_manager = MagicMock()
    flow_blocker = MagicMock()

    def _mock_issue_loader(n: int) -> None:
        return None

    def _mock_flow_context(n: int) -> tuple[str, None]:
        return (flow_context_branch, None)

    queue_persistence = MagicMock()
    queue_persistence.frozen_queue = None
    check_service = MagicMock()
    if check_result is not None:
        check_service.verify_branch.return_value = check_result

    coordinator = GlobalDispatchCoordinator(
        config=config,
        capacity=capacity,
        github=github,
        store=store,
        flow_manager=flow_manager,
        flow_blocker=flow_blocker,
        queue_persistence=queue_persistence,
        issue_loader=_mock_issue_loader,
        flow_context_resolver=_mock_flow_context,
        queue_selector=MagicMock(return_value=[]),
        check_service=check_service,
    )

    return coordinator, {
        "flow_blocker": flow_blocker,
        "store": store,
        "check_service": check_service,
    }


def make_issue(
    number: int,
    *,
    title: str | None = None,
    state: IssueState = IssueState.READY,
    labels: list[str] | None = None,
    github_state: str = "OPEN",
) -> IssueInfo:
    """Create an IssueInfo for health check tests."""
    return IssueInfo(
        number=number,
        title=title or f"Test Issue {number}",
        state=state,
        labels=labels or [state.to_label()],
        github_state=github_state,
    )


def make_check_result(
    *,
    is_valid: bool = True,
    issues: list[str] | None = None,
    branch: str = "task/issue-42",
) -> CheckResult:
    """Create a CheckResult for health check tests."""
    return CheckResult(is_valid=is_valid, issues=issues or [], branch=branch)
