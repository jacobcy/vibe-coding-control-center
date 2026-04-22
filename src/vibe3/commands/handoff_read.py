"""Handoff read commands - List and show handoff information."""

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
from vibe3.ui.handoff_ui import (
    render_handoff_detail,
    render_handoff_list,
    render_handoff_summary,
)
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


def list_handoffs(
    branch: Annotated[
        str | None,
        typer.Option("--branch", "-b", help="Flow/branch to inspect"),
    ] = None,
    kind: Annotated[
        str | None,
        typer.Option("--kind", "-k", help="Filter by kind: plan/run/review/indicate"),
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

        allowed_kinds = {"plan", "run", "review", "indicate"}
        filter_kind = kind.lower() if kind else None
        if filter_kind and filter_kind not in allowed_kinds:
            typer.echo(
                "Error: --kind must be one of: plan, run, review, indicate", err=True
            )
            raise typer.Exit(1)

        handoffs: list[dict[str, str]] = []
        stats = {"total": 0, "plans": 0, "runs": 0, "reviews": 0, "indicates": 0}

        for event in events:
            # Map event types back to handoff kinds
            # handoff_plan    -> plan
            # handoff_report  -> run
            # handoff_review  -> review  (reviewer raw output artifact, new)
            # handoff_audit   -> review  (reviewer-initiated authoritative audit, new)
            # audit_recorded  -> review  (system auto-generated minimal audit, legacy)
            # handoff_indicate -> indicate
            event_type_to_kind = {
                "handoff_plan": "plan",
                "handoff_report": "run",
                "handoff_run": "run",  # backward-compat: old event type
                "handoff_review": "review",  # new: reviewer raw output artifact
                "handoff_audit": "review",  # new: reviewer-initiated audit
                "audit_recorded": "review",  # legacy: system auto-generated
                # (backward-compat)
                "handoff_indicate": "indicate",
            }
            event_kind = event_type_to_kind.get(event.event_type)
            if event_kind is None:
                # Skip non-handoff events
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
            elif event_kind == "indicate":
                stats["indicates"] += 1

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

        # Show pending indicate action (manager dispatch hint)
        if state.latest_indicate_action:
            console.print("[bold]## Pending Dispatch[/]")
            console.print(
                f"  [cyan]indicate_action:[/] [yellow]{state.latest_indicate_action}[/]"
                "  [dim](executor will consume on next dispatch)[/]"
            )
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
