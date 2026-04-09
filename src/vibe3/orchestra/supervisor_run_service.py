"""Supervisor execution service.

This module handles supervisor mode execution for governance tasks
and issue processing.
"""

from __future__ import annotations

import os
from pathlib import Path

import typer

from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.execution.contracts import ExecutionRequest
from vibe3.execution.coordinator import ExecutionCoordinator
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.orchestra.services.governance_service import GovernanceService
from vibe3.runtime.agent_resolver import resolve_supervisor_agent_options
from vibe3.services.orchestra_status_service import OrchestraStatusService

SUPERVISOR_APPLY_TASK = (
    "Run supervisor/apply task. "
    "Process the provided supervisor material or governance issue only, "
    "perform the minimal allowed actions, then stop. "
    "Do not switch into governance scan or run/plan/review execution modes."
)


def run_supervisor_mode(
    *,
    supervisor_file: str,
    issue_number: int | None,
    dry_run: bool,
    async_mode: bool,
) -> None:
    """Execute supervisor run mode.

    Args:
        supervisor_file: Path to supervisor markdown file
        issue_number: Optional GitHub issue number
        dry_run: If True, only render and print the plan
        async_mode: If True, run in async mode (tmux session)
    """
    config = OrchestraConfig.from_settings()
    governance_cfg = config.governance.model_copy(
        update={
            "supervisor_file": supervisor_file,
            "prompt_template": config.supervisor_handoff.prompt_template,
            "include_supervisor_content": True,
            "dry_run": dry_run,
        }
    )
    config = config.model_copy(update={"governance": governance_cfg})
    from vibe3.manager.flow_manager import FlowManager

    service = GovernanceService(
        config=config,
        status_service=OrchestraStatusService(config, orchestrator=FlowManager(config)),
    )
    plan_text = service.render_current_plan()

    if dry_run:
        typer.echo(f"-> Supervisor dry run: {supervisor_file}")
        typer.echo(plan_text)
        return

    options = resolve_supervisor_agent_options(config)
    run_task = (
        build_supervisor_task(
            config=config,
            issue_number=issue_number,
        )
        or SUPERVISOR_APPLY_TASK
    )
    typer.echo(f"-> Supervisor run: {supervisor_file}")
    if async_mode:
        store = SQLiteClient()
        coordinator = ExecutionCoordinator(config, store, CodeagentBackend())

        safe_name = Path(supervisor_file).stem.replace("/", "-")
        execution_name = f"vibe3-supervisor-{safe_name}"
        if issue_number is not None:
            execution_name = f"{execution_name}-issue-{issue_number}"

        request = ExecutionRequest(
            role="supervisor",
            target_branch=f"issue-{issue_number}" if issue_number else "supervisor",
            target_id=issue_number or 0,
            execution_name=execution_name,
            prompt=plan_text,
            options=options,
            env={**os.environ, "VIBE3_ASYNC_CHILD": "1"},
            refs={"task": run_task},
            actor="orchestra:supervisor",
            mode="async",
        )

        try:
            result = coordinator.dispatch_execution(request)
            if not result.launched:
                typer.echo(f"Supervisor dispatch queued/throttled: {result.reason}")
                return

            typer.echo(f"Tmux session: {result.tmux_session}")
            typer.echo(f"Session log: {result.log_path}")
            return
        except BaseException as exc:
            typer.echo(f"Error: supervisor async start failed: {exc}", err=True)
            raise typer.Exit(1) from exc

    sync_request = ExecutionRequest(
        role="supervisor",
        target_branch=f"issue-{issue_number}" if issue_number else "supervisor",
        target_id=issue_number or 0,
        execution_name=(
            f"vibe3-supervisor-{Path(supervisor_file).stem.replace('/', '-')}"
        ),
        prompt=plan_text,
        options=options,
        refs={"task": run_task},
        actor="orchestra:supervisor",
        mode="sync",
        dry_run=False,
    )
    sync_result = ExecutionCoordinator(
        config,
        SQLiteClient(),
        CodeagentBackend(),
    ).dispatch_execution(sync_request)
    if not sync_result.launched:
        raise typer.Exit(1)


def build_supervisor_task(
    *,
    config: OrchestraConfig,
    issue_number: int | None,
) -> str | None:
    """Build supervisor task description for issue processing.

    Args:
        config: Orchestra configuration
        issue_number: GitHub issue number (optional)

    Returns:
        Task description string or None if no issue number
    """
    if issue_number is None:
        return None
    repo_hint = f" in repo {config.repo}" if config.repo else ""
    issue_title = f"issue #{issue_number}"
    issue = GitHubClient().view_issue(issue_number, repo=config.repo)
    if isinstance(issue, dict):
        raw_title = issue.get("title")
        if isinstance(raw_title, str) and raw_title.strip():
            issue_title = raw_title.strip()
    return (
        f"Process governance issue #{issue_number}{repo_hint}: {issue_title}\n"
        "This issue has already been handed to the current supervisor explicitly.\n"
        "Read the issue directly, verify the findings, perform the allowed actions, "
        "comment the outcome on the same issue, and close it when complete."
    )


def resolve_issue_supervisor_file() -> str:
    """Resolve the supervisor file for issue processing.

    Returns:
        Supervisor file path from orchestra config
    """
    return OrchestraConfig.from_settings().supervisor_handoff.supervisor_file
