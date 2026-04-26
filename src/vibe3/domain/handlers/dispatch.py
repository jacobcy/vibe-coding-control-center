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
from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.domain.events import (
    ExecutorDispatchIntent,
    PlannerDispatchIntent,
    ReviewerDispatchIntent,
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
    actor: str,
    **builder_kwargs: object,
) -> None:
    """Dispatch a role intent through role request builder + ExecutionCoordinator."""
    config = load_orchestra_config()
    store = SQLiteClient()
    issue = _load_issue_info(config, issue_number)

    logger.bind(
        domain=handler_domain,
        issue_number=issue_number,
    ).debug(f"Building {role} request")

    request = request_builder(config, issue, **builder_kwargs)

    coordinator = ExecutionCoordinator(config, store)

    # Record dispatch intent BEFORE execution (correct chronological order)
    branch_arg = builder_kwargs.get("branch")
    branch = str(branch_arg) if branch_arg else ""
    if branch:
        store.add_event(
            branch,
            f"{role}_dispatched",
            actor,
            detail=f"{role.capitalize()} dispatched",
            refs={
                "issue": str(issue_number),
                "role": role,
            },
        )

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


def handle_planner_dispatch_intent(event: PlannerDispatchIntent) -> None:
    """Handle PlannerDispatchIntent event via role request builder."""
    store = SQLiteClient()
    flow_state = store.get_flow_state(event.branch) if event.branch else None
    has_plan = bool(flow_state and flow_state.get("plan_ref")) if flow_state else False

    logger.bind(
        domain="planner_handler",
        issue_number=event.issue_number,
        branch=event.branch,
        retry=has_plan,
    ).info("Planner dispatch triggered")

    try:
        _dispatch_role_intent(
            role="planner",
            handler_domain="planner_handler",
            issue_number=event.issue_number,
            request_builder=build_plan_request,
            actor=event.actor,
            branch=event.branch,
        )
    except Exception as exc:
        logger.bind(
            domain="planner_handler",
            issue_number=event.issue_number,
        ).exception(f"Planner dispatch failed: {exc}")
        # Propagate exception to event system for proper handling
        raise


def handle_executor_dispatch_intent(event: ExecutorDispatchIntent) -> None:
    """Handle ExecutorDispatchIntent event via role request builder.

    Enriches the neutral dispatch intent with execution-specific context
    (plan_ref, audit_ref, commit_mode) read from flow state.

    commit_mode is derived from trigger_state: when the executor is dispatched
    with state/merge-ready, it enters the publish path automatically.
    """
    store = SQLiteClient()

    # Read execution context from flow state
    flow_state = store.get_flow_state(event.branch) if event.branch else None
    plan_ref = str(v) if flow_state and (v := flow_state.get("plan_ref")) else None
    audit_ref = str(v) if flow_state and (v := flow_state.get("audit_ref")) else None

    # publish path is determined solely by trigger_state == merge-ready
    commit_mode = event.trigger_state == "merge-ready"

    logger.bind(
        domain="executor_handler",
        issue_number=event.issue_number,
        branch=event.branch,
        plan_ref=plan_ref,
        commit_mode=commit_mode,
    ).info("Executor dispatch triggered")

    try:
        _dispatch_role_intent(
            role="executor",
            handler_domain="executor_handler",
            issue_number=event.issue_number,
            request_builder=build_run_request,
            actor=event.actor,
            branch=event.branch,
            plan_ref=plan_ref,
            audit_ref=audit_ref,
            commit_mode=commit_mode,
        )
    except Exception as exc:
        logger.bind(
            domain="executor_handler",
            issue_number=event.issue_number,
        ).exception(f"Executor dispatch failed: {exc}")
        # Propagate exception to event system for proper handling
        raise


def handle_reviewer_dispatch_intent(event: ReviewerDispatchIntent) -> None:
    """Handle ReviewerDispatchIntent event via role request builder.

    Enriches the neutral dispatch intent with report_ref and retry context
    read from flow state.
    """
    store = SQLiteClient()

    # Read execution context from flow state
    flow_state = store.get_flow_state(event.branch) if event.branch else None
    report_ref = str(v) if flow_state and (v := flow_state.get("report_ref")) else None
    has_audit = (
        bool(flow_state and flow_state.get("audit_ref")) if flow_state else False
    )

    logger.bind(
        domain="reviewer_handler",
        issue_number=event.issue_number,
        branch=event.branch,
        report_ref=report_ref,
        retry=has_audit,
    ).info("Reviewer dispatch triggered")

    try:
        _dispatch_role_intent(
            role="reviewer",
            handler_domain="reviewer_handler",
            issue_number=event.issue_number,
            request_builder=build_review_request,
            actor=event.actor,
            branch=event.branch,
            report_ref=report_ref,
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
    from typing import cast

    from vibe3.domain.publisher import subscribe

    # Subscribe to new event names
    subscribe(
        "PlannerDispatchIntent",
        cast(Callable[[DomainEvent], None], handle_planner_dispatch_intent),
    )
    subscribe(
        "ExecutorDispatchIntent",
        cast(Callable[[DomainEvent], None], handle_executor_dispatch_intent),
    )
    subscribe(
        "ReviewerDispatchIntent",
        cast(Callable[[DomainEvent], None], handle_reviewer_dispatch_intent),
    )

    # Backward compatibility: subscribe to old event names
    subscribe(
        "PlannerDispatched",
        cast(Callable[[DomainEvent], None], handle_planner_dispatch_intent),
    )
    subscribe(
        "ExecutorDispatched",
        cast(Callable[[DomainEvent], None], handle_executor_dispatch_intent),
    )
    subscribe(
        "ReviewerDispatched",
        cast(Callable[[DomainEvent], None], handle_reviewer_dispatch_intent),
    )

    logger.bind(domain="events").info("Dispatch-intent event handlers registered")
