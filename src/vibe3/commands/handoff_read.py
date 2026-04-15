"""Handoff read commands - List and show handoff information."""

import json
from pathlib import Path
from typing import Annotated

import typer
from loguru import logger

from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.commands.common import trace_scope
from vibe3.environment.session_registry import SessionRegistryService
from vibe3.models.flow import FlowEvent, FlowState
from vibe3.services.flow_service import FlowService
from vibe3.services.handoff_service import HandoffService
from vibe3.ui.console import console
from vibe3.ui.handoff_ui import (
    render_handoff_detail,
    render_handoff_list,
    render_handoff_summary,
)
from vibe3.utils.git_helpers import get_branch_handoff_dir
from vibe3.utils.issue_branch_resolver import resolve_issue_branch_input

UPDATE_LOG_MESSAGE_PREVIEW_LIMIT = 80


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


def _resolve_ref_path(val: str | None, _worktree_root: str | None = None) -> str:
    """Resolve ref value to absolute path if needed, but prefer relative.

    For file paths, returns the original relative path if it's already
    relative. For absolute paths, keeps them absolute (e.g., URLs).

    Args:
        val: The reference value (could be relative path, absolute path,
            URL, etc.)
        _worktree_root: The worktree root path (unused, kept for
            signature compatibility)

    Returns:
        Display-friendly path (relative preferred for file refs)
    """
    # Note: _worktree_root intentionally unused - display relative paths
    _ = _worktree_root  # Mark as intentionally unused for type checker

    if not val or Path(val).is_absolute() or val.startswith("("):
        return val or ""
    # For relative file paths, return as-is (cleaner display)
    return val


def _render_agent_chain(
    state: FlowState,
    live_sessions: list[dict] | None = None,
    worktree_root: str | None = None,
) -> None:
    console.print("[bold]Agent Chain[/]")
    for label, actor_label in [
        ("spec_ref", "planner_actor"),
        ("plan_ref", "planner_actor"),
        ("report_ref", "executor_actor"),
        ("audit_ref", "reviewer_actor"),
    ]:
        val = getattr(state, label, None)
        actor = getattr(state, actor_label, None) or ""
        actor_str = f"  [dim]{actor}[/]" if actor else ""
        # Display relative paths for cleaner output (absolute paths are too long)
        display_val: str = _resolve_ref_path(val, worktree_root)
        if display_val:
            # Print label + actor on one line, then path on its own line.
            # This prevents terminal-width wrapping from mixing the actor
            # into the path continuation (e.g. "...executio\nn-report.md  develop").
            # Use overflow='ellipsis' to show truncation explicitly if path is too long.
            label_line = f"  [dim]{label}[/]{actor_str}"
            console.print(label_line)
            console.print(f"    {display_val}", no_wrap=True, overflow="ellipsis")
        else:
            console.print(f"  [dim]{label}[/]  [dim](pending)[/]")
    console.print()

    # Show live registry sessions (registry is the source of truth)
    if live_sessions:
        console.print("[bold]Live Sessions (registry)[/]")
        for sess in live_sessions:
            role = sess.get("role", "")
            name = sess.get("session_name", "")
            status = sess.get("status", "")
            console.print(f"  [green]{role}[/]  {name}  [dim]{status}[/]")
        console.print()


def _render_handoff_events(events: list[FlowEvent]) -> None:
    if not events:
        console.print("[dim]  no handoff events[/]")
        return

    for event in reversed(events):
        time_str = event.created_at[:19].replace("T", " ")
        console.print(
            f"[dim]{time_str}[/]  [magenta]{event.event_type}[/]  [dim]{event.actor}[/]"
        )
        if event.detail:
            console.print(f"  {event.detail}")
        if event.refs:
            files = event.refs.get("files") if isinstance(event.refs, dict) else None
            if files and isinstance(files, list):
                for f in files:
                    console.print(f"  [dim]- {f}[/]")
            ref = event.refs.get("ref") if isinstance(event.refs, dict) else None
            if ref:
                console.print(f"  [dim]- {ref}[/]")
        console.print()


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


def _preview_update_message(message: str, truncate: bool) -> str:
    if not truncate or len(message) <= UPDATE_LOG_MESSAGE_PREVIEW_LIMIT:
        return message
    return message[:UPDATE_LOG_MESSAGE_PREVIEW_LIMIT] + "..."


def _render_updates_log(updates: list[dict[str, str]], truncate: bool = True) -> None:
    """Render updates in log format."""
    if not updates:
        console.print("[dim]  no updates yet[/]")
        return

    kind_colors = {"finding": "yellow", "blocker": "red", "next": "blue", "note": "dim"}
    for update in updates:
        timestamp = update["timestamp"]
        actor = update["actor"]
        kind = update["kind"]
        message = update["message"]
        kind_color = kind_colors.get(kind, "dim")
        time_str = timestamp[:19].replace("T", " ")
        console.print(f"[dim]{time_str}[/]  [{kind_color}]{kind}[/]  [dim]{actor}[/]")
        if message:
            for msg_line in _preview_update_message(message, truncate).split("\n"):
                console.print(f"  {msg_line}")
        console.print()


def list_handoffs(
    branch: Annotated[
        str | None,
        typer.Option("--branch", "-b", help="Flow/branch to inspect"),
    ] = None,
    kind: Annotated[
        str | None,
        typer.Option("--kind", "-k", help="Filter by kind: plan/run/review"),
    ] = None,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
) -> None:
    """List handoff events for current or specified branch."""
    with trace_scope(trace, "handoff list", domain="handoff"):
        flow_service = FlowService()
        handoff_service = HandoffService(store=flow_service.store)

        target_branch = branch if branch else flow_service.get_current_branch()
        events = handoff_service.get_handoff_events(target_branch)

        allowed_kinds = {"plan", "run", "review"}
        filter_kind = kind.lower() if kind else None
        if filter_kind and filter_kind not in allowed_kinds:
            typer.echo("Error: --kind must be one of: plan, run, review", err=True)
            raise typer.Exit(1)

        handoffs: list[dict[str, str]] = []
        stats = {"total": 0, "plans": 0, "runs": 0, "reviews": 0}

        for event in events:
            event_kind = event.event_type.replace("handoff_", "", 1)
            if event_kind not in allowed_kinds:
                continue
            if filter_kind and event_kind != filter_kind:
                continue

            stats["total"] += 1
            if event_kind == "plan":
                stats["plans"] += 1
            elif event_kind == "run":
                stats["runs"] += 1
            elif event_kind == "review":
                stats["reviews"] += 1

            handoffs.append(
                {
                    "timestamp": event.created_at[:19].replace("T", " "),
                    "kind": event_kind,
                    "actor": event.actor,
                    "detail": event.detail or "",
                }
            )

        render_handoff_list(target_branch, handoffs)
        render_handoff_summary(target_branch, stats)


def show(
    branch: Annotated[str | None, typer.Argument(help="Branch name")] = None,
    artifact: Annotated[
        Path | None,
        typer.Option("--artifact", help="Display a handoff artifact file"),
    ] = None,
    show_all: Annotated[bool, typer.Option("--all", help="显示全部历史")] = False,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
) -> None:
    """Show agent handoff chain and events."""
    with trace_scope(trace, "handoff show", domain="handoff"):
        if artifact is not None:
            if not artifact.exists():
                typer.echo(f"Error: artifact not found: {artifact}", err=True)
                raise typer.Exit(1)
            if not artifact.is_file():
                typer.echo(f"Error: artifact is not a file: {artifact}", err=True)
                raise typer.Exit(1)
            try:
                render_handoff_detail(artifact)
            except (OSError, UnicodeDecodeError) as exc:
                typer.echo(f"Error: failed to read artifact: {exc}", err=True)
                raise typer.Exit(1)
            return

        logger.bind(command="handoff show", branch=branch).info(
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
        console.print()
        _render_agent_chain(
            state, live_sessions=live_sessions, worktree_root=worktree_root
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
        _render_handoff_events(handoff_events)

        # Show current.md updates in log format
        git_dir = service.get_git_common_dir()
        handoff_dir = get_branch_handoff_dir(git_dir, target_branch)
        current_md = handoff_dir / "current.md"

        console.print("[bold]--- Update Log (current.md) ---[/]")
        console.print(f"  [dim]path[/]  {current_md}")
        console.print()

        if current_md.exists():
            content = current_md.read_text(encoding="utf-8")
            updates = _parse_updates_section(content)
            _render_updates_log(updates, truncate=not show_all)

            # Show full content hint
            console.print("[dim]---[/]")
            console.print(f"[dim]Full file: {current_md}[/]")
            console.print("[dim]Use 'cat' or edit the file to see all sections[/]")
        else:
            console.print(
                "[dim]  (current.md not found — run `vibe3 handoff init` to create)[/]"
            )
        console.print()
