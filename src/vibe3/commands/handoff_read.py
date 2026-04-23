"""Handoff read commands - status and artifact display."""

import json
from pathlib import Path
from typing import Annotated

import typer
from loguru import logger

from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.commands.common import trace_scope
from vibe3.commands.handoff_render import (
    _render_agent_chain,
    _render_handoff_events,
    _render_updates_log,
)
from vibe3.environment.session_registry import SessionRegistryService
from vibe3.services.flow_service import FlowService
from vibe3.services.handoff_service import HandoffService
from vibe3.services.verdict_service import VerdictService
from vibe3.ui.console import console
from vibe3.ui.flow_ui_primitives import resolve_ref_path
from vibe3.ui.handoff_ui import render_handoff_detail
from vibe3.utils.git_helpers import get_branch_handoff_dir
from vibe3.utils.issue_branch_resolver import resolve_issue_branch_input


def _get_live_sessions_for_branch(store: SQLiteClient, branch: str) -> list[dict]:
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


def _parse_updates_section(content: str) -> list[dict[str, str]]:
    """Parse Updates section from current.md content."""
    updates: list[dict[str, str]] = []
    in_updates = False

    for line in content.split("\n"):
        if line.strip() == "## Updates":
            in_updates = True
            continue
        if in_updates and line.startswith("## "):
            break
        if in_updates and line.startswith("### "):
            try:
                header = line[4:].strip()
                parts = header.split(" | ")
                if len(parts) >= 3:
                    updates.append(
                        {
                            "timestamp": parts[0].strip(),
                            "actor": parts[1].strip(),
                            "kind": parts[2].strip(),
                            "message": "",
                        }
                    )
            except Exception as e:
                logger.debug(f"Skipping item: {e}")
                continue
        elif in_updates and updates and line.strip():
            if updates[-1]["message"]:
                updates[-1]["message"] += "\n" + line
            else:
                updates[-1]["message"] = line
    return updates


def show(
    artifact: Annotated[Path, typer.Argument(help="Shared handoff artifact path")],
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
) -> None:
    """Show a shared handoff artifact file."""
    with trace_scope(trace, "handoff show", domain="handoff"):
        resolved_artifact = artifact
        service = FlowService()

        if not resolved_artifact.exists():
            try:
                git_common = Path(service.get_git_common_dir())
                if git_common:
                    potential = git_common / artifact
                    if potential.exists():
                        resolved_artifact = potential
            except Exception:
                pass

        if not resolved_artifact.exists():
            typer.echo(f"Error: artifact not found: {artifact}", err=True)
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
            except RuntimeError as error:
                typer.echo(f"Error: {error}", err=True)
                raise typer.Exit(1) from error
        else:
            target_branch = service.get_current_branch()

        state = service.get_flow_state(target_branch)
        if not state:
            logger.error(f"Flow not found: {target_branch}")
            raise typer.Exit(1)

        limit = None if show_all else 5
        handoff_events = handoff_service.get_handoff_events(target_branch, limit=limit)

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

        _render_agent_chain(
            state,
            store=service.store,
            live_sessions=live_sessions,
            worktree_root=worktree_root,
        )

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

        console.print("[bold]--- Recent Handoff Events ---[/]")
        console.print()
        _render_handoff_events(handoff_events, worktree_root=worktree_root)

        # Show current.md updates in log format
        git_dir = service.get_git_common_dir()
        handoff_dir = get_branch_handoff_dir(git_dir, target_branch)
        current_md = handoff_dir / "current.md"

        console.print("[bold]--- Update Log (current.md) ---[/]")
        current_md_display = resolve_ref_path(str(current_md))
        console.print(f"  [dim]path[/]  {current_md_display}")
        console.print()

        if current_md.exists():
            content = current_md.read_text(encoding="utf-8")
            updates = _parse_updates_section(content)
            _render_updates_log(updates, truncate=not show_all)

            # Show full content hint
            console.print("[dim]---[/]")
            console.print(f"[dim]Artifact: {current_md_display}[/]")
            console.print(
                "[dim]Use `vibe3 handoff show <path>` "
                "to inspect the full shared file[/]"
            )
        else:
            console.print(
                "[dim]  (current.md not found — run `vibe3 handoff init` to create)[/]"
            )
        console.print()
