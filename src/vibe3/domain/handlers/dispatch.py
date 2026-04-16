"""Event handlers for agent dispatch-intent events.

Handlers for planner, executor, and reviewer dispatch.
These handlers listen to dispatch-intent events and trigger actual execution
through role request builders from src/vibe3/roles/.
"""

from __future__ import annotations

from typing import Callable

from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.domain.events import (
    ExecutorDispatched,
    PlannerDispatched,
    ReviewerDispatched,
)
from vibe3.domain.events.flow_lifecycle import DomainEvent
from vibe3.execution.contracts import ExecutionRequest
from vibe3.execution.coordinator import ExecutionCoordinator
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo
from vibe3.roles.plan import build_plan_request
from vibe3.roles.review import build_review_request
from vibe3.roles.run import build_run_request

_RequestBuilder = Callable[..., ExecutionRequest]


def _load_issue_info(config: OrchestraConfig, issue_number: int) -> IssueInfo:
    """Load issue info for dispatch."""
    issue_payload = GitHubClient().view_issue(issue_number, repo=config.repo)
    if not isinstance(issue_payload, dict):
        return IssueInfo(
            number=issue_number,
            title=f"Issue {issue_number}",
            labels=[],
        )

    issue = IssueInfo.from_github_payload(issue_payload)
    if issue is not None:
        return issue

    title = str(issue_payload.get("title") or f"Issue {issue_number}")
    labels = [
        label.get("name", "")
        for label in issue_payload.get("labels", [])
        if isinstance(label, dict)
    ]
    return IssueInfo(number=issue_number, title=title, labels=labels)


def _dispatch_role_intent(
    *,
    role: str,
    handler_domain: str,
    issue_number: int,
    request_builder: _RequestBuilder,
    **builder_kwargs: object,
) -> None:
    """Dispatch a role intent through role request builder + ExecutionCoordinator."""
    config = OrchestraConfig.from_settings()
    store = SQLiteClient()
    issue = _load_issue_info(config, issue_number)

    logger.bind(
        domain=handler_domain,
        issue_number=issue_number,
    ).debug(f"Building {role} request")

    request = request_builder(config, issue, **builder_kwargs)

    coordinator = ExecutionCoordinator(config, store)
    result = coordinator.dispatch_execution(request)

    if result.launched:
        logger.bind(
            domain=handler_domain,
            issue_number=issue_number,
            tmux_session=result.tmux_session,
        ).success(f"{role.capitalize()} dispatch completed")
        return

    if result.skipped:
        logger.bind(
            domain=handler_domain,
            issue_number=issue_number,
        ).info(f"{role.capitalize()} dispatch skipped: {result.reason}")
        return

    logger.bind(
        domain=handler_domain,
        issue_number=issue_number,
    ).warning(f"{role.capitalize()} dispatch not launched: {result.reason}")


def handle_planner_dispatched(event: PlannerDispatched) -> None:
    """Handle PlannerDispatched event via role request builder."""
    logger.bind(
        domain="planner_handler",
        issue_number=event.issue_number,
        branch=event.branch,
    ).info("Planner dispatch triggered")

    try:
        _dispatch_role_intent(
            role="planner",
            handler_domain="planner_handler",
            issue_number=event.issue_number,
            request_builder=build_plan_request,
            branch=event.branch,
        )
    except Exception as exc:
        logger.bind(
            domain="planner_handler",
            issue_number=event.issue_number,
        ).exception(f"Planner dispatch failed: {exc}")
        # Propagate exception to event system for proper handling
        raise


def handle_executor_dispatched(event: ExecutorDispatched) -> None:
    """Handle ExecutorDispatched event via role request builder."""
    logger.bind(
        domain="executor_handler",
        issue_number=event.issue_number,
        branch=event.branch,
        plan_ref=event.plan_ref,
    ).info("Executor dispatch triggered")

    try:
        _dispatch_role_intent(
            role="executor",
            handler_domain="executor_handler",
            issue_number=event.issue_number,
            request_builder=build_run_request,
            branch=event.branch,
            plan_ref=event.plan_ref,
            audit_ref=event.audit_ref,
            commit_mode=event.commit_mode,
        )
    except Exception as exc:
        logger.bind(
            domain="executor_handler",
            issue_number=event.issue_number,
        ).exception(f"Executor dispatch failed: {exc}")
        # Propagate exception to event system for proper handling
        raise


def handle_reviewer_dispatched(event: ReviewerDispatched) -> None:
    """Handle ReviewerDispatched event via role request builder."""
    logger.bind(
        domain="reviewer_handler",
        issue_number=event.issue_number,
        branch=event.branch,
        report_ref=event.report_ref,
    ).info("Reviewer dispatch triggered")

    try:
        _dispatch_role_intent(
            role="reviewer",
            handler_domain="reviewer_handler",
            issue_number=event.issue_number,
            request_builder=build_review_request,
            branch=event.branch,
            report_ref=event.report_ref,
        )
    except Exception as exc:
        logger.bind(
            domain="reviewer_handler",
            issue_number=event.issue_number,
        ).exception(f"Reviewer dispatch failed: {exc}")
        # Propagate exception to event system for proper handling
        raise


def register_dispatch_handlers() -> None:
    """Register all dispatch-intent event handlers."""
    from typing import Callable, cast

    from vibe3.domain.publisher import subscribe

    subscribe(
        "PlannerDispatched",
        cast(Callable[[DomainEvent], None], handle_planner_dispatched),
    )
    subscribe(
        "ExecutorDispatched",
        cast(Callable[[DomainEvent], None], handle_executor_dispatched),
    )
    subscribe(
        "ReviewerDispatched",
        cast(Callable[[DomainEvent], None], handle_reviewer_dispatched),
    )

    logger.bind(domain="events").info("Dispatch-intent event handlers registered")
