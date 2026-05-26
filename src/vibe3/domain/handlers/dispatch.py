"""Event handlers for agent dispatch-intent events.

Handlers for planner, executor, and reviewer dispatch.
These handlers listen to dispatch-intent events and trigger actual execution
through role request builders from src/vibe3/roles/.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

from loguru import logger

from vibe3.clients.store_context import get_store
from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.domain.events import (
    ExecutorDispatchIntent,
    PlannerDispatchIntent,
    ReviewerDispatchIntent,
)
from vibe3.domain.handler_registry import register_handler
from vibe3.execution.contracts import ExecutionRequest
from vibe3.execution.coordinator import ExecutionCoordinator
from vibe3.roles.plan import build_plan_request
from vibe3.roles.review import build_review_request
from vibe3.roles.run import build_run_request
from vibe3.services.flow_service import FlowService
from vibe3.services.issue_context_loader import load_issue_info

_RequestBuilder = Callable[..., ExecutionRequest]

_BLOCKED_SCOPE_PREFIXES = (".claude/", ".codex/")
_FILES_LINE_RE = re.compile(r"^\s*-?\s*Files:\s*(.+)$", re.IGNORECASE | re.MULTILINE)


def _validate_plan_scope(plan_ref: str | None) -> list[str]:
    """Parse plan Files: lines and return any .claude/ or .codex/ paths found.

    Returns empty list if plan_ref is None, plan file is unreadable,
    or no blocked paths are found.
    """
    if not plan_ref:
        return []

    plan_path = _resolve_plan_path(plan_ref)
    if plan_path is None:
        return []

    try:
        content = plan_path.read_text(encoding="utf-8")
    except OSError:
        return []

    blocked: list[str] = []
    for match in _FILES_LINE_RE.finditer(content):
        files_text = match.group(1).strip()
        for raw in files_text.split(","):
            path = raw.strip().strip("[]").strip().strip("'\"")
            if path and path.startswith(_BLOCKED_SCOPE_PREFIXES):
                blocked.append(path)

    return blocked


def _resolve_plan_path(plan_ref: str) -> Path | None:
    """Resolve plan_ref to an absolute file path. Returns None on failure."""
    plan_path = Path(plan_ref)
    if plan_path.is_absolute() and plan_path.is_file():
        return plan_path
    cwd_path = Path.cwd() / plan_ref
    if cwd_path.is_file():
        return cwd_path
    return None


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

    with get_store() as store:
        issue = load_issue_info(issue_number, config=config)

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

        # Not launched, not skipped:
        # - capacity_full / duplicate_dispatch → normal throttling (info)
        # - all other failures → warning (FailedGate will control)
        # Dispatch failures do NOT trigger flow block.
        # Flow block is determined by business logic only
        # (noop_gate, dependencies, loops).
        # FailedGate controls dispatch based on error severity.
        reason_code = result.reason_code or "unknown"

        if reason_code in ("capacity_full", "duplicate_dispatch"):
            # Normal throttling/dedup - log at info level
            logger.bind(
                domain=handler_domain,
                issue_number=issue_number,
                reason_code=reason_code,
            ).info(f"{role.capitalize()} dispatch deferred: {result.reason}")
        else:
            # Unexpected failure - record to error_log and log warning
            # FailedGate will control dispatch based on threshold
            from vibe3.services.error_helpers import record_error

            error_message = f"{role} dispatch failed: {result.reason}"
            try:
                record_error(
                    error_code="E_DISPATCH_FAILURE",
                    error_message=error_message,
                    issue_number=issue_number,
                    branch=branch,
                    store=store,
                )
            except Exception as exc:
                logger.bind(
                    domain=handler_domain,
                    issue_number=issue_number,
                ).warning(f"Failed to record dispatch error: {exc}")

            logger.bind(
                domain=handler_domain,
                issue_number=issue_number,
                reason_code=reason_code,
            ).warning(
                f"{role.capitalize()} dispatch failed: {result.reason} - "
                "FailedGate will control dispatch"
            )


@register_handler("PlannerDispatchIntent")
def handle_planner_dispatch_intent(event: PlannerDispatchIntent, /) -> None:
    """Handle PlannerDispatchIntent event via role request builder."""
    with get_store() as store:
        flow_state = store.get_flow_state(event.branch) if event.branch else None
        has_plan = (
            bool(flow_state and flow_state.get("plan_ref")) if flow_state else False
        )

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
            tick_id=event.tick_id,
        )
    except Exception as exc:
        logger.bind(
            domain="planner_handler",
            issue_number=event.issue_number,
        ).exception(f"Planner dispatch failed: {exc}")
        # Propagate exception to event system for proper handling
        raise


@register_handler("ExecutorDispatchIntent")
def handle_executor_dispatch_intent(event: ExecutorDispatchIntent, /) -> None:
    """Handle ExecutorDispatchIntent event via role request builder.

    Enriches the neutral dispatch intent with execution-specific context
    (plan_ref, audit_ref, commit_mode) read from flow state.

    commit_mode is derived from trigger_state: when the executor is dispatched
    with state/merge-ready, it enters the publish path automatically.
    """
    with get_store() as store:
        # Read execution context from flow state
        flow_state = store.get_flow_state(event.branch) if event.branch else None
        plan_ref = str(v) if flow_state and (v := flow_state.get("plan_ref")) else None
        audit_ref = (
            str(v) if flow_state and (v := flow_state.get("audit_ref")) else None
        )

    # publish path is determined solely by trigger_state == merge-ready
    commit_mode = event.trigger_state == "merge-ready"

    logger.bind(
        domain="executor_handler",
        issue_number=event.issue_number,
        branch=event.branch,
        plan_ref=plan_ref,
        commit_mode=commit_mode,
    ).info("Executor dispatch triggered")

    # Validate plan scope before dispatch
    blocked_paths = _validate_plan_scope(plan_ref)
    if blocked_paths:
        logger.bind(
            domain="executor_handler",
            issue_number=event.issue_number,
            branch=event.branch,
            blocked_paths=blocked_paths,
        ).warning("Plan references blocked .claude/.codex paths, blocking flow")

        FlowService().block_flow(
            event.branch,
            reason=(
                "Plan modifies .claude/.codex files: "
                + ", ".join(blocked_paths)
                + ". Executor sandbox cannot write to agent definition directories."
            ),
            actor="orchestra:scope-gate",
        )
        return

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
            tick_id=event.tick_id,
        )
    except Exception as exc:
        logger.bind(
            domain="executor_handler",
            issue_number=event.issue_number,
        ).exception(f"Executor dispatch failed: {exc}")
        # Propagate exception to event system for proper handling
        raise


@register_handler("ReviewerDispatchIntent")
def handle_reviewer_dispatch_intent(event: ReviewerDispatchIntent, /) -> None:
    """Handle ReviewerDispatchIntent event via role request builder.

    Enriches the neutral dispatch intent with report_ref and retry context
    read from flow state.
    """
    with get_store() as store:
        # Read execution context from flow state
        flow_state = store.get_flow_state(event.branch) if event.branch else None
        report_ref = (
            str(v) if flow_state and (v := flow_state.get("report_ref")) else None
        )
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
            tick_id=event.tick_id,
        )
    except Exception as exc:
        logger.bind(
            domain="reviewer_handler",
            issue_number=event.issue_number,
        ).exception(f"Reviewer dispatch failed: {exc}")
        # Propagate exception to event system for proper handling
        raise
