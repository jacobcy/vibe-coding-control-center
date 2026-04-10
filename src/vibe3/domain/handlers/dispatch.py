"""Event handlers for agent dispatch-intent events.

Handlers for planner, executor, and reviewer dispatch.
These handlers listen to dispatch-intent events and trigger actual execution.
"""

import os
from pathlib import Path
from typing import Callable

from loguru import logger

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.domain.events import (
    ExecutorDispatched,
    PlannerDispatched,
    ReviewerDispatched,
)
from vibe3.domain.events.flow_lifecycle import DomainEvent
from vibe3.environment.worktree import WorktreeManager
from vibe3.execution.contracts import ExecutionRequest
from vibe3.execution.coordinator import ExecutionCoordinator
from vibe3.execution.flow_dispatch import FlowManager
from vibe3.models.orchestra_config import OrchestraConfig


def _current_cli_entry() -> str:
    """Resolve the CLI entry point."""
    return "src/vibe3/cli.py"


def _current_repo_root() -> str:
    """Resolve the current repository root."""
    return str(Path.cwd())


def _resolve_dispatch_cwd(
    *,
    config: OrchestraConfig,
    store: SQLiteClient,
    issue_number: int,
    fallback_branch: str,
) -> str | None:
    """Resolve worktree cwd for a role dispatch."""
    flow_manager = FlowManager(config, store=store)
    flow = flow_manager.get_flow_for_issue(issue_number)
    branch = str(flow.get("branch") or "").strip() if flow else fallback_branch
    if not branch:
        return None

    cwd = WorktreeManager(
        config,
        Path.cwd(),
        flow_manager=flow_manager,
    )._resolve_manager_cwd(issue_number, branch)[0]
    return str(cwd) if cwd else None


def _dispatch_agent_intent(
    *,
    role: str,
    handler_domain: str,
    issue_number: int,
    branch: str,
    cmd: list[str],
    refs: dict[str, str],
) -> None:
    """Dispatch a planner/executor/reviewer intent through ExecutionCoordinator."""
    config = OrchestraConfig.from_settings()
    store = SQLiteClient()
    coordinator = ExecutionCoordinator(config, store)

    logger.bind(
        domain=handler_domain,
        issue_number=issue_number,
        cmd=" ".join(cmd),
    ).debug(f"Executing {role} command")

    request = ExecutionRequest(
        role=role,  # type: ignore[arg-type]
        target_branch=branch,
        target_id=issue_number,
        execution_name=f"vibe3-{role}-issue-{issue_number}",
        cmd=cmd,
        cwd=_resolve_dispatch_cwd(
            config=config,
            store=store,
            issue_number=issue_number,
            fallback_branch=branch,
        ),
        env={**os.environ, "VIBE3_ASYNC_CHILD": "1"},
        refs=refs,
        actor=f"orchestra:{role}",
        mode="async",
    )

    result = coordinator.dispatch_execution(request)
    if result.launched:
        logger.bind(
            domain=handler_domain,
            issue_number=issue_number,
            tmux_session=result.tmux_session,
        ).success(f"{role.capitalize()} dispatch completed")
        return

    logger.bind(
        domain=handler_domain,
        issue_number=issue_number,
    ).warning(f"{role.capitalize()} dispatch not launched: {result.reason}")


def handle_planner_dispatched(event: PlannerDispatched) -> None:
    """Handle PlannerDispatched event.

    Triggers planner execution when plan trigger is activated.
    Uses ExecutionCoordinator to execute CLI command.
    """
    logger.bind(
        domain="planner_handler",
        issue_number=event.issue_number,
        branch=event.branch,
    ).info("Planner dispatch triggered")

    try:
        cmd = [
            "uv",
            "run",
            "--project",
            _current_repo_root(),
            "python",
            "-I",
            _current_cli_entry(),
            "plan",
            "--issue",
            str(event.issue_number),
            "--no-async",
        ]
        _dispatch_agent_intent(
            role="planner",
            handler_domain="planner_handler",
            issue_number=event.issue_number,
            branch=event.branch,
            cmd=cmd,
            refs={"issue_number": str(event.issue_number)},
        )
    except Exception as exc:
        logger.bind(
            domain="planner_handler",
            issue_number=event.issue_number,
        ).exception(f"Planner dispatch failed: {exc}")


def handle_executor_dispatched(event: ExecutorDispatched) -> None:
    """Handle ExecutorDispatched event.

    Triggers executor execution when run trigger is activated.
    Uses ExecutionCoordinator to execute CLI command.
    """
    logger.bind(
        domain="executor_handler",
        issue_number=event.issue_number,
        branch=event.branch,
        plan_ref=event.plan_ref,
    ).info("Executor dispatch triggered")

    try:
        cmd = [
            "uv",
            "run",
            "--project",
            _current_repo_root(),
            "python",
            "-I",
            _current_cli_entry(),
            "run",
            "--issue",
            str(event.issue_number),
            "--no-async",
        ]

        if event.plan_ref:
            cmd.extend(["--plan-ref", event.plan_ref])

        refs = {"issue_number": str(event.issue_number)}
        if event.plan_ref:
            refs["plan_ref"] = event.plan_ref
        _dispatch_agent_intent(
            role="executor",
            handler_domain="executor_handler",
            issue_number=event.issue_number,
            branch=event.branch,
            cmd=cmd,
            refs=refs,
        )
    except Exception as exc:
        logger.bind(
            domain="executor_handler",
            issue_number=event.issue_number,
        ).exception(f"Executor dispatch failed: {exc}")


def handle_reviewer_dispatched(event: ReviewerDispatched) -> None:
    """Handle ReviewerDispatched event.

    Triggers reviewer execution when review trigger is activated.
    Uses ExecutionCoordinator to execute CLI command.
    """
    logger.bind(
        domain="reviewer_handler",
        issue_number=event.issue_number,
        branch=event.branch,
        report_ref=event.report_ref,
    ).info("Reviewer dispatch triggered")

    try:
        cmd = [
            "uv",
            "run",
            "--project",
            _current_repo_root(),
            "python",
            "-I",
            _current_cli_entry(),
            "review",
            "--issue",
            str(event.issue_number),
            "--no-async",
        ]

        if event.report_ref:
            cmd.extend(["--report-ref", event.report_ref])

        refs = {"issue_number": str(event.issue_number)}
        if event.report_ref:
            refs["report_ref"] = event.report_ref
        _dispatch_agent_intent(
            role="reviewer",
            handler_domain="reviewer_handler",
            issue_number=event.issue_number,
            branch=event.branch,
            cmd=cmd,
            refs=refs,
        )
    except Exception as exc:
        logger.bind(
            domain="reviewer_handler",
            issue_number=event.issue_number,
        ).exception(f"Reviewer dispatch failed: {exc}")


def register_dispatch_handlers() -> None:
    """Register all dispatch-intent event handlers."""
    from typing import cast

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
