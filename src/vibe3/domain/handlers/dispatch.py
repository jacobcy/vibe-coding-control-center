"""Event handlers for agent dispatch-intent events.

Handlers for planner, executor, and reviewer dispatch.
These handlers listen to dispatch-intent events and trigger actual execution.
"""

import os
from typing import Callable

from loguru import logger

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.domain.events import (
    ExecutorDispatched,
    PlannerDispatched,
    ReviewerDispatched,
)
from vibe3.domain.events.flow_lifecycle import DomainEvent
from vibe3.execution.contracts import ExecutionRequest
from vibe3.execution.coordinator import ExecutionCoordinator
from vibe3.manager.manager_executor import ManagerExecutor
from vibe3.models.orchestra_config import OrchestraConfig


def _current_cli_entry() -> str:
    """Resolve the CLI entry point."""
    return "src/vibe3/cli.py"


def _current_repo_root() -> str:
    """Resolve the current repository root."""
    from pathlib import Path

    return str(Path.cwd())


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

    config = OrchestraConfig.from_settings()
    store = SQLiteClient()
    coordinator = ExecutionCoordinator(config, store)

    try:
        cli_entry = _current_cli_entry()
        repo_root = _current_repo_root()
        cmd = [
            "uv",
            "run",
            "--project",
            repo_root,
            "python",
            "-I",
            cli_entry,
            "plan",
            "--issue",
            str(event.issue_number),
            "--no-async",
        ]

        logger.bind(
            domain="planner_handler",
            issue_number=event.issue_number,
            cmd=" ".join(cmd),
        ).debug("Executing planner command")

        manager = ManagerExecutor(config, dry_run=config.dry_run)

        # Resolve CWD (worktree path)
        from pathlib import Path

        repo_path = Path.cwd()
        flow = manager.flow_manager.get_flow_for_issue(event.issue_number)
        if flow:
            branch = str(flow.get("branch") or "").strip()
            if branch:
                from vibe3.environment.worktree import WorktreeManager

                worktree_manager = WorktreeManager(config, repo_path)
                cwd_result = worktree_manager._resolve_manager_cwd(
                    event.issue_number, branch
                )
                cwd = cwd_result[0] if cwd_result else None
            else:
                cwd_result = manager._resolve_manager_cwd(event.issue_number, branch)
                cwd = cwd_result[0] if cwd_result else None
        else:
            cwd_result = manager._resolve_manager_cwd(event.issue_number, event.branch)
            cwd = cwd_result[0] if cwd_result else None

        request = ExecutionRequest(
            role="planner",
            target_branch=event.branch,
            target_id=event.issue_number,
            execution_name=f"vibe3-planner-issue-{event.issue_number}",
            cmd=cmd,
            cwd=str(cwd) if cwd else None,
            env={**os.environ, "VIBE3_ASYNC_CHILD": "1"},
            refs={"issue_number": str(event.issue_number)},
            actor="orchestra:planner",
            mode="async",
        )

        result = coordinator.dispatch_execution(request)

        if result.launched:
            logger.bind(
                domain="planner_handler",
                issue_number=event.issue_number,
                tmux_session=result.tmux_session,
            ).success("Planner dispatch completed")
        else:
            logger.bind(
                domain="planner_handler",
                issue_number=event.issue_number,
            ).warning(f"Planner dispatch not launched: {result.reason}")

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

    config = OrchestraConfig.from_settings()
    store = SQLiteClient()
    coordinator = ExecutionCoordinator(config, store)

    try:
        cli_entry = _current_cli_entry()
        repo_root = _current_repo_root()
        cmd = [
            "uv",
            "run",
            "--project",
            repo_root,
            "python",
            "-I",
            cli_entry,
            "run",
            "--issue",
            str(event.issue_number),
            "--no-async",
        ]

        if event.plan_ref:
            cmd.extend(["--plan-ref", event.plan_ref])

        logger.bind(
            domain="executor_handler",
            issue_number=event.issue_number,
            cmd=" ".join(cmd),
        ).debug("Executing executor command")

        manager = ManagerExecutor(config, dry_run=config.dry_run)

        # Resolve CWD (worktree path)
        from pathlib import Path

        repo_path = Path.cwd()
        flow = manager.flow_manager.get_flow_for_issue(event.issue_number)
        if flow:
            branch = str(flow.get("branch") or "").strip()
            if branch:
                from vibe3.environment.worktree import WorktreeManager

                worktree_manager = WorktreeManager(config, repo_path)
                cwd_result = worktree_manager._resolve_manager_cwd(
                    event.issue_number, branch
                )
                cwd = cwd_result[0] if cwd_result else None
            else:
                cwd_result = manager._resolve_manager_cwd(event.issue_number, branch)
                cwd = cwd_result[0] if cwd_result else None
        else:
            cwd_result = manager._resolve_manager_cwd(event.issue_number, event.branch)
            cwd = cwd_result[0] if cwd_result else None

        refs = {"issue_number": str(event.issue_number)}
        if event.plan_ref:
            refs["plan_ref"] = event.plan_ref

        request = ExecutionRequest(
            role="executor",
            target_branch=event.branch,
            target_id=event.issue_number,
            execution_name=f"vibe3-executor-issue-{event.issue_number}",
            cmd=cmd,
            cwd=str(cwd) if cwd else None,
            env={**os.environ, "VIBE3_ASYNC_CHILD": "1"},
            refs=refs,
            actor="orchestra:executor",
            mode="async",
        )

        result = coordinator.dispatch_execution(request)

        if result.launched:
            logger.bind(
                domain="executor_handler",
                issue_number=event.issue_number,
                tmux_session=result.tmux_session,
            ).success("Executor dispatch completed")
        else:
            logger.bind(
                domain="executor_handler",
                issue_number=event.issue_number,
            ).warning(f"Executor dispatch not launched: {result.reason}")

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

    config = OrchestraConfig.from_settings()
    store = SQLiteClient()
    coordinator = ExecutionCoordinator(config, store)

    try:
        cli_entry = _current_cli_entry()
        repo_root = _current_repo_root()
        cmd = [
            "uv",
            "run",
            "--project",
            repo_root,
            "python",
            "-I",
            cli_entry,
            "review",
            "--issue",
            str(event.issue_number),
            "--no-async",
        ]

        if event.report_ref:
            cmd.extend(["--report-ref", event.report_ref])

        logger.bind(
            domain="reviewer_handler",
            issue_number=event.issue_number,
            cmd=" ".join(cmd),
        ).debug("Executing reviewer command")

        manager = ManagerExecutor(config, dry_run=config.dry_run)

        # Resolve CWD (worktree path)
        from pathlib import Path

        repo_path = Path.cwd()
        flow = manager.flow_manager.get_flow_for_issue(event.issue_number)
        if flow:
            branch = str(flow.get("branch") or "").strip()
            if branch:
                from vibe3.environment.worktree import WorktreeManager

                worktree_manager = WorktreeManager(config, repo_path)
                cwd_result = worktree_manager._resolve_manager_cwd(
                    event.issue_number, branch
                )
                cwd = cwd_result[0] if cwd_result else None
            else:
                cwd_result = manager._resolve_manager_cwd(event.issue_number, branch)
                cwd = cwd_result[0] if cwd_result else None
        else:
            cwd_result = manager._resolve_manager_cwd(event.issue_number, event.branch)
            cwd = cwd_result[0] if cwd_result else None

        refs = {"issue_number": str(event.issue_number)}
        if event.report_ref:
            refs["report_ref"] = event.report_ref

        request = ExecutionRequest(
            role="reviewer",
            target_branch=event.branch,
            target_id=event.issue_number,
            execution_name=f"vibe3-reviewer-issue-{event.issue_number}",
            cmd=cmd,
            cwd=str(cwd) if cwd else None,
            env={**os.environ, "VIBE3_ASYNC_CHILD": "1"},
            refs=refs,
            actor="orchestra:reviewer",
            mode="async",
        )

        result = coordinator.dispatch_execution(request)

        if result.launched:
            logger.bind(
                domain="reviewer_handler",
                issue_number=event.issue_number,
                tmux_session=result.tmux_session,
            ).success("Reviewer dispatch completed")
        else:
            logger.bind(
                domain="reviewer_handler",
                issue_number=event.issue_number,
            ).warning(f"Reviewer dispatch not launched: {result.reason}")

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
