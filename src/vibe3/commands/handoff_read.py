"""Handoff read commands - status and artifact display."""

import json
from datetime import datetime, timezone
from types import ModuleType
from typing import Annotated

import typer
from loguru import logger

from vibe3.clients import GitClient
from vibe3.commands.command_options import FormatOption, VerboseOption
from vibe3.commands.common import enable_method_trace
from vibe3.commands.handoff_render import (
    _render_handoff_events,
)
from vibe3.exceptions import SystemError, UserError
from vibe3.services.flow_service import FlowService
from vibe3.services.handoff_status_service import HandoffStatusService
from vibe3.services.issue_branch_resolver import resolve_issue_branch_input
from vibe3.services.pr_branch_resolver import resolve_command_branch
from vibe3.ui.console import console
from vibe3.ui.handoff_ui import render_handoff_detail


def _format_relative_time(timestamp: datetime, now: datetime | None = None) -> str:
    """Format datetime as human-readable relative time.

    Args:
        timestamp: Datetime to format
        now: Optional fixed timestamp for testing (defaults to
            datetime.now(timezone.utc))

    Returns:
        Human-readable string like "2 hours ago", "3 days ago", etc.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        # Assume UTC if no timezone
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    delta = now - timestamp
    seconds = int(delta.total_seconds())

    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif seconds < 2592000:  # 30 days
        days = seconds // 86400
        return f"{days} day{'s' if days != 1 else ''} ago"
    else:
        months = seconds // 2592000
        return f"{months} month{'s' if months != 1 else ''} ago"


_HANDOFF_SHOW_HELP = """\
Usage: vibe3 handoff show <target> [--branch <branch>]

Show a handoff artifact by target reference.

Target formats:
  @vibe/<path>       Vibe3 installation materials (governance docs, prompts, skills)
  @key               Shared artifact key (e.g. @task-476/run-1.md)
  @plan              Flow plan ref (resolved from flow_state.plan_ref)
  @report            Flow report ref (resolved from flow_state.report_ref)
  @audit             Flow audit ref (resolved from flow_state.audit_ref)
  relative/path      Canonical worktree ref; defaults to current worktree,
                     use --branch for strict resolution
  /abs/path          Absolute filesystem path (debug fallback)

Examples:
  vibe3 handoff show @vibe/supervisor/apply.md
  vibe3 handoff show @vibe/prompts/vibe-commit.md --vibe-dir /path/to/vibe3
  vibe3 handoff show @task-476/run-1.md
  vibe3 handoff show @plan --branch task/issue-822
  vibe3 handoff show @plan
  vibe3 handoff show --branch task/issue-476 docs/reports/audit.md
  vibe3 handoff show /abs/path/to/artifact.md

See also:
  vibe3 handoff status          Show current flow handoff chain
  vibe3 handoff append "<msg>"  Append a handoff record
"""


def _get_yaml() -> ModuleType:
    """Lazy import yaml to avoid unconditional import cost."""
    import yaml

    return yaml


def show(
    target: Annotated[
        str | None,
        typer.Argument(
            help="Handoff target: @vibe/<path>, @key, relative/path, or /abs/path"
        ),
    ] = None,
    branch: Annotated[
        str | None,
        typer.Option("--branch", help="Branch for canonical ref resolution"),
    ] = None,
    vibe_dir: Annotated[
        str | None,
        typer.Option(
            "--vibe-dir", help="Explicit vibe3 installation path for @vibe/ targets"
        ),
    ] = None,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪（set VIBE3_TRACE=1）")
    ] = False,
) -> None:
    """Show a handoff artifact.

    Supports @vibe/<path>, @key, relative/path, and /abs/path targets.
    """
    if trace:
        enable_method_trace()

    from vibe3.services.path_helpers import resolve_handoff_target

    if target is None:
        typer.echo(_HANDOFF_SHOW_HELP)
        raise typer.Exit(0)

    # Resolve numeric issue ID → canonical branch name before path lookup
    resolved_branch: str | None = None
    if branch is not None:
        try:
            resolved_branch = (
                resolve_issue_branch_input(branch, FlowService()) or branch
            )
        except (UserError, SystemError) as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(1)
    try:
        resolved_artifact = resolve_handoff_target(
            target, resolved_branch, git_client=GitClient(), vibe_dir=vibe_dir
        )
    except FileNotFoundError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    if not resolved_artifact.is_file():
        typer.echo(f"Error: artifact is not a file: {resolved_artifact}", err=True)
        raise typer.Exit(1)
    try:
        render_handoff_detail(resolved_artifact)
    except (OSError, UnicodeDecodeError) as exc:
        typer.echo(f"Error: failed to read artifact: {exc}", err=True)
        raise typer.Exit(1)


def status(
    branch_arg: Annotated[str | None, typer.Argument(help="Branch name")] = None,
    branch_opt: Annotated[
        str | None, typer.Option("--branch", help="Branch name or issue number")
    ] = None,
    pr_opt: Annotated[
        int | None,
        typer.Option("--pr", help="PR number to resolve branch from"),
    ] = None,
    show_all: Annotated[bool, typer.Option("--all", help="显示全部历史")] = False,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪（set VIBE3_TRACE=1）")
    ] = False,
    output_format: FormatOption = "table",
    verbose: VerboseOption = False,
) -> None:
    """Show current flow handoff status and recent records."""
    if trace:
        enable_method_trace()

    flow_service = FlowService()
    try:
        target_branch = resolve_command_branch(
            branch_opt=branch_opt,
            pr_opt=pr_opt,
            position_arg=branch_arg,
            flow_service=flow_service,
        )
    except (UserError, SystemError) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error

    logger.bind(command="handoff status", branch=target_branch).info(
        "Showing handoff details"
    )

    # Aggregate handoff status from service
    status_service = HandoffStatusService(flow_service=flow_service)
    limit = None if show_all else 2
    try:
        result = status_service.get_handoff_status(target_branch, limit=limit)
    except ValueError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error

    if output_format == "json":
        output = {
            "state": result.state.model_dump(),
            "events": [e.model_dump() for e in result.events],
            "recent_updates": result.recent_updates,
        }
        typer.echo(json.dumps(output, indent=2, default=str))
        return

    if output_format == "yaml":
        output = {
            "state": result.state.model_dump(),
            "events": [e.model_dump() for e in result.events],
            "recent_updates": result.recent_updates,
        }
        typer.echo(
            _get_yaml().dump(output, default_flow_style=False, allow_unicode=True)
        )
        return

    # Table format (default)
    console.print(f"\n[bold cyan]flow[/]: {result.flow_slug}")

    # Show worktree path for context (where files actually live)
    if result.worktree_root:
        console.print(f"[dim]worktree: {result.worktree_root}[/]")
    console.print()

    # Show recent updates from handoff file
    if result.recent_updates:
        console.print("[bold]--- Recent Handoff Updates ---[/]")
        console.print()
        for update in reversed(result.recent_updates):
            timestamp = update["timestamp"][:19].replace("T", " ")
            actor = update["actor"]
            kind = update["kind"]
            message = update["message"].split("\n")[0]  # First line only
            console.print(f"[dim]{timestamp}[/]  [cyan]{kind}[/]  [dim]{actor}[/]")
            console.print(f"  {message}")
            console.print()

    # Show latest verdict at the top
    if result.latest_verdict:
        console.print("[bold]## Latest Verdict[/]")
        console.print(f"  [cyan]verdict:[/] {result.latest_verdict.verdict}")
        console.print(f"  [cyan]actor:[/] {result.latest_verdict.actor}")
        console.print(f"  [cyan]role:[/] {result.latest_verdict.role}")
        # Human-friendly timestamp (relative time)
        timestamp_str = _format_relative_time(result.latest_verdict.timestamp)
        console.print(f"  [cyan]timestamp:[/] {timestamp_str}")
        if result.latest_verdict.reason:
            console.print(f"  [cyan]reason:[/] {result.latest_verdict.reason}")
        if result.latest_verdict.issues:
            console.print(f"  [cyan]issues:[/] {result.latest_verdict.issues}")
        console.print()

    # Show resume hints from registry only (registry is source of truth)
    if result.live_sessions:
        hints_shown = False
        for sess in result.live_sessions:
            backend_session_id = sess.get("backend_session_id")
            if backend_session_id:
                if not hints_shown:
                    console.print("[bold]Resume Hints[/]")
                    hints_shown = True
                console.print(
                    f'  [dim]codeagent-wrapper resume {backend_session_id} "..."[/]'
                )
        if hints_shown:
            console.print()

    console.print("[bold]--- Successful Handoff Events ---[/]")
    console.print()
    _render_handoff_events(
        result.events,
        worktree_root=result.worktree_root,
        branch=target_branch,
        verbose=verbose,
    )
    if not show_all and (result.events or result.recent_updates):
        # Conditionally add --branch hint if viewing different branch
        current_branch = flow_service.get_current_branch()
        tip_cmd = "vibe3 handoff show @current"
        if target_branch != current_branch:
            tip_cmd += f" --branch {target_branch}"
        console.print(
            f"[dim]Tip: use '{tip_cmd}' to view full handoff content, "
            "or 'vibe3 handoff status --all' to show all events.[/]"
        )


def register_read_commands(app: typer.Typer) -> None:
    """Register read-only handoff commands."""
    app.command()(show)
    app.command()(status)
