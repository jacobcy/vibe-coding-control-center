"""Handoff read commands - status and artifact display."""

import json
from typing import Annotated, Any

import typer
from loguru import logger

from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.clients.git_client import get_git_client
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.commands.common import trace_scope
from vibe3.commands.handoff_render import (
    _render_handoff_events,
)
from vibe3.environment.session_registry import SessionRegistryService
from vibe3.exceptions import SystemError, UserError
from vibe3.services.flow_service import FlowService
from vibe3.services.handoff_service import HandoffService
from vibe3.services.verdict_service import VerdictService
from vibe3.ui.console import console
from vibe3.ui.handoff_ui import render_handoff_detail
from vibe3.utils.issue_branch_resolver import resolve_issue_branch_input


def _get_live_sessions_for_branch(
    store: SQLiteClient, branch: str
) -> list[dict[str, Any]]:
    """Return truly live runtime sessions from the registry for a given branch.

    This function confirms tmux liveness for each session, unlike
    store.list_live_runtime_sessions which only checks status.

    Args:
        store: SQLiteClient instance for database access.
        branch: The branch to filter sessions by.

    Returns:
        List of session dicts that are truly live.
    """
    backend = CodeagentBackend()
    registry = SessionRegistryService(store=store, backend=backend)
    return registry.get_truly_live_sessions_for_branch(branch)


_HANDOFF_SHOW_HELP = """\
Usage: vibe3 handoff show <target> [--branch <branch>]

Show a handoff artifact by target reference.

Target formats:
  @key               Shared artifact key (e.g. @task-476/run-1.md)
  relative/path      Canonical worktree ref; requires --branch <branch>
  /abs/path          Absolute filesystem path (debug fallback)

Examples:
  vibe3 handoff show @task-476/run-1.md
  vibe3 handoff show --branch task/issue-476 docs/reports/audit.md
  vibe3 handoff show /abs/path/to/artifact.md

See also:
  vibe3 handoff status          Show current flow handoff chain
  vibe3 handoff append "<msg>"  Append a handoff record
"""


def show(
    target: Annotated[
        str | None,
        typer.Argument(help="Handoff target: @key, relative/path, or /abs/path"),
    ] = None,
    branch: Annotated[
        str | None,
        typer.Option("--branch", help="Branch for canonical ref resolution"),
    ] = None,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
) -> None:
    """Show a handoff artifact. Supports @key, relative/path, and /abs/path targets."""
    from vibe3.utils.path_helpers import resolve_handoff_target

    if target is None:
        typer.echo(_HANDOFF_SHOW_HELP)
        raise typer.Exit(0)

    with trace_scope(trace, "handoff show", domain="handoff"):
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
                target, resolved_branch, git_client=get_git_client()
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
    branch: Annotated[str | None, typer.Argument(help="Branch name")] = None,
    show_all: Annotated[bool, typer.Option("--all", help="显示全部历史")] = False,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
) -> None:
    """Show current flow handoff status and recent records."""
    with trace_scope(trace, "handoff status", domain="handoff"):
        logger.bind(command="handoff status", branch=branch).info(
            "Showing handoff details"
        )

        service = FlowService()
        handoff_service = HandoffService(store=service.store)
        if branch:
            try:
                target_branch = resolve_issue_branch_input(branch, service) or branch
            except (UserError, SystemError) as error:
                typer.echo(f"Error: {error}", err=True)
                raise typer.Exit(1) from error
        else:
            target_branch = service.get_current_branch()

        state = service.get_flow_state(target_branch)
        if not state:
            logger.error(f"Flow not found: {target_branch}")
            raise typer.Exit(1)

        limit = None if show_all else 5
        handoff_events = handoff_service.get_success_handoff_events(
            target_branch, limit=limit
        )

        if json_output:
            output = {
                "state": state.model_dump(),
                "events": [e.model_dump() for e in handoff_events],
            }
            typer.echo(json.dumps(output, indent=2, default=str))
            return

        # Fetch live registry sessions (preferred over deprecated FlowState fields)
        live_sessions = _get_live_sessions_for_branch(service.store, target_branch)

        # Resolve worktree root for the target branch, not the current
        # command execution context
        worktree_path = service.git_client.find_worktree_path_for_branch(target_branch)
        if worktree_path:
            worktree_root = str(worktree_path)
        else:
            # Fallback: if branch has no dedicated worktree, use current
            worktree_root = service.git_client.get_worktree_root()

        console.print(f"\n[bold cyan]flow[/]: {state.flow_slug}")

        # Show worktree path for context (where files actually live)
        if worktree_path:
            console.print(f"[dim]worktree: {worktree_root}[/]")
        console.print()

        # Show latest verdict at the top
        verdict_service = VerdictService(store=service.store)
        latest_verdict = verdict_service.get_latest_verdict(target_branch)
        if latest_verdict:
            console.print("[bold]## Latest Verdict[/]")
            console.print(f"  [cyan]verdict:[/] {latest_verdict.verdict}")
            console.print(f"  [cyan]actor:[/] {latest_verdict.actor}")
            console.print(f"  [cyan]role:[/] {latest_verdict.role}")
            console.print(
                f"  [cyan]timestamp:[/] {latest_verdict.timestamp.isoformat()}"
            )
            if latest_verdict.reason:
                console.print(f"  [cyan]reason:[/] {latest_verdict.reason}")
            if latest_verdict.issues:
                console.print(f"  [cyan]issues:[/] {latest_verdict.issues}")
            console.print()

        # Show resume hints from registry only (registry is source of truth)
        if live_sessions:
            hints_shown = False
            for sess in live_sessions:
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
            handoff_events, worktree_root=worktree_root, branch=target_branch
        )


def register_read_commands(app: typer.Typer) -> None:
    """Register read-only handoff commands."""
    app.command()(show)
    app.command()(status)
