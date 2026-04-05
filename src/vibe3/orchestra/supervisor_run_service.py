"""Supervisor execution service.

This module handles supervisor mode execution for governance tasks
and issue processing.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.agents.runner import CodeagentExecutionService
from vibe3.clients.github_client import GitHubClient
from vibe3.config.settings import VibeConfig
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.services.governance_service import GovernanceService
from vibe3.orchestra.services.status_service import OrchestraStatusService

if TYPE_CHECKING:
    pass


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

    runtime_config = VibeConfig.get_defaults()
    options = CodeagentExecutionService(runtime_config).resolve_agent_options("run")
    run_task = build_supervisor_task(
        config=config,
        issue_number=issue_number,
    ) or (runtime_config.run.run_prompt or "Execute governance supervisor task")
    backend = CodeagentBackend()

    typer.echo(f"-> Supervisor run: {supervisor_file}")
    if async_mode:
        safe_name = Path(supervisor_file).stem.replace("/", "-")
        execution_name = f"vibe3-supervisor-{safe_name}"
        if issue_number is not None:
            execution_name = f"{execution_name}-issue-{issue_number}"
        handle = backend.start_async(
            prompt=plan_text,
            options=options,
            task=run_task,
            execution_name=execution_name,
            env={**os.environ, "VIBE3_ASYNC_CHILD": "1"},
        )
        typer.echo(f"Tmux session: {handle.tmux_session}")
        typer.echo(f"Session log: {handle.log_path}")
        return

    result = backend.run(
        prompt=plan_text,
        options=options,
        task=run_task,
        dry_run=False,
    )
    if not result.is_success():
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
