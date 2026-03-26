"""Handoff command - Agent handoff chain and events."""

import json
from contextlib import nullcontext
from pathlib import Path
from typing import Annotated

import typer
from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.models.flow import FlowEvent, FlowState
from vibe3.observability.logger import setup_logging
from vibe3.observability.trace import trace_context
from vibe3.services.handoff_service import HandoffService
from vibe3.ui.console import console
from vibe3.ui.handoff_ui import (
    render_handoff_detail,
    render_handoff_list,
    render_handoff_summary,
)
from vibe3.utils.git_helpers import get_branch_handoff_dir

app = typer.Typer(
    help="Agent handoff chain and events",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def _trace_scope(trace: bool, command: str):  # type: ignore[no-untyped-def]
    if trace:
        setup_logging(verbose=2)
        return trace_context(command=command, domain="handoff")
    return nullcontext()


def _record_handoff_reference(
    *,
    command: str,
    ref_label: str,
    ref_value: str,
    next_step: str | None,
    blocked_by: str | None,
    actor: str,
    trace: bool,
    method_name: str,
) -> None:
    with _trace_scope(trace, command):
        specific_ref_key = f"{ref_label.lower()}_ref"
        logger.bind(
            command=command,
            actor=actor,
            ref=ref_value,
            **{specific_ref_key: ref_value},
        ).info(f"Recording {ref_label} handoff")

        service = HandoffService()
        method = getattr(service, method_name)
        method(ref_value, next_step, blocked_by, actor)
        console.print(f"[green]✓[/] {ref_label} handoff recorded: {ref_value}")


def _render_agent_chain(state: FlowState) -> None:
    console.print("[bold]═══ Agent Chain ═══[/]")
    for label, actor_label, session_label in [
        ("spec_ref", "planner_actor", "planner_session_id"),
        ("plan_ref", "planner_actor", "planner_session_id"),
        ("report_ref", "executor_actor", "executor_session_id"),
        ("audit_ref", "reviewer_actor", "reviewer_session_id"),
    ]:
        val = getattr(state, label, None)
        actor = getattr(state, actor_label, None) or ""
        session_id = getattr(state, session_label, None)
        actor_str = f"  [dim]{actor}[/]" if actor else ""
        session_str = f" [blue]({session_id[:8]})[/]" if session_id else ""
        status = val if val else "[dim](pending)[/]"
        console.print(f"  [dim]{label}[/]  {status}{actor_str}{session_str}")
    console.print()


def _render_handoff_events(events: list[FlowEvent]) -> None:
    if not events:
        console.print("[dim]  no handoff events[/]")
        return

    for event in events:
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
                    console.print(f"  [dim]📎 {f}[/]")
            ref = event.refs.get("ref") if isinstance(event.refs, dict) else None
            if ref:
                console.print(f"  [dim]📎 {ref}[/]")
        console.print()


def _parse_updates_section(content: str) -> list[dict[str, str]]:
    """Parse Updates section from current.md content.

    Args:
        content: Full content of current.md

    Returns:
        List of update entries with timestamp, actor, kind, message
    """
    updates: list[dict[str, str]] = []
    in_updates = False

    for line in content.split("\n"):
        if line.strip() == "## Updates":
            in_updates = True
            continue

        if in_updates and line.startswith("## "):
            # Reached next section, stop parsing
            break

        if in_updates and line.startswith("### "):
            # Parse update header: ### timestamp | actor | kind
            try:
                header = line[4:].strip()
                parts = header.split(" | ")
                if len(parts) >= 3:
                    timestamp = parts[0].strip()
                    actor = parts[1].strip()
                    kind = parts[2].strip()
                    updates.append(
                        {
                            "timestamp": timestamp,
                            "actor": actor,
                            "kind": kind,
                            "message": "",
                        }
                    )
            except Exception:
                pass
        elif in_updates and updates and line.strip():
            # Append message to last update
            if updates[-1]["message"]:
                updates[-1]["message"] += "\n" + line
            else:
                updates[-1]["message"] = line

    return updates


def _render_updates_log(updates: list[dict[str, str]]) -> None:
    """Render updates in log format.

    Args:
        updates: List of update entries
    """
    if not updates:
        console.print("[dim]  no updates yet[/]")
        return

    # Display in reverse chronological order (newest first)
    for update in reversed(updates):
        timestamp = update["timestamp"]
        actor = update["actor"]
        kind = update["kind"]
        message = update["message"]

        # Kind-based color coding
        kind_colors = {
            "finding": "yellow",
            "blocker": "red",
            "next": "blue",
            "note": "dim",
        }
        kind_color = kind_colors.get(kind, "dim")

        time_str = timestamp[:19].replace("T", " ")
        console.print(f"[dim]{time_str}[/]  [{kind_color}]{kind}[/]  [dim]{actor}[/]")
        if message:
            for msg_line in message.split("\n"):
                console.print(f"  {msg_line}")
        console.print()


@app.command()
def init(
    force: Annotated[bool, typer.Option("--yes", "-y", help="Force overwrite")] = False,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
) -> None:
    """Initialize handoff file for current branch."""
    with _trace_scope(trace, "handoff init"):
        logger.bind(command="handoff init", force=force).info("Initializing handoff")

        service = HandoffService()
        handoff_path = service.ensure_current_handoff(force=force)

        console.print(f"[green]✓[/] Handoff file ready: {handoff_path}")


@app.command("list")
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
    with _trace_scope(trace, "handoff list"):
        git = GitClient()
        store = SQLiteClient()

        target_branch = branch if branch else git.get_current_branch()
        events_data = store.get_events(target_branch, event_type_prefix="handoff_")

        allowed_kinds = {"plan", "run", "review"}
        filter_kind = kind.lower() if kind else None
        if filter_kind and filter_kind not in allowed_kinds:
            typer.echo("Error: --kind must be one of: plan, run, review", err=True)
            raise typer.Exit(1)

        handoffs: list[dict[str, str]] = []
        stats = {"total": 0, "plans": 0, "runs": 0, "reviews": 0}

        for event in events_data:
            event_type = event.get("event_type", "")
            event_kind = event_type.replace("handoff_", "", 1)
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
                    "timestamp": str(event.get("created_at", ""))[:19].replace(
                        "T", " "
                    ),
                    "kind": event_kind,
                    "actor": str(event.get("actor", "")),
                    "detail": str(event.get("detail", "")),
                }
            )

        render_handoff_list(target_branch, handoffs)
        render_handoff_summary(target_branch, stats)


@app.command()
def show(
    flow_name: Annotated[str | None, typer.Argument(help="Flow to show")] = None,
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
    with _trace_scope(trace, "handoff show"):
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

        logger.bind(command="handoff show", flow_name=flow_name).info(
            "Showing handoff details"
        )

        git = GitClient()
        store = SQLiteClient()
        branch = flow_name if flow_name else git.get_current_branch()

        state_data = store.get_flow_state(branch)
        if not state_data:
            logger.error(f"Flow not found: {branch}")
            raise typer.Exit(1)

        state = FlowState(**state_data)
        # When --all, pass None to get all events; otherwise limit to 5
        limit = None if show_all else 5
        events_data = store.get_events(
            branch, event_type_prefix="handoff_", limit=limit
        )
        handoff_events = [FlowEvent(**e) for e in events_data]

        if json_output:
            output = {
                "state": state.model_dump(),
                "events": [e.model_dump() for e in handoff_events],
            }
            typer.echo(json.dumps(output, indent=2, default=str))
            return

        console.print(f"\n[bold cyan]flow[/]: {state.flow_slug}")
        console.print()
        _render_agent_chain(state)

        # Show resume hints if session IDs exist
        hints_shown = False
        for role, session_id in [
            ("planner", state.planner_session_id),
            ("executor", state.executor_session_id),
            ("reviewer", state.reviewer_session_id),
        ]:
            if session_id:
                if not hints_shown:
                    console.print("[bold]💡 Resume Hints[/]")
                    hints_shown = True
                console.print(f'  [dim]codeagent-wrapper resume {session_id} "..."[/]')

        if hints_shown:
            console.print()

        console.print("[bold]═══ Recent Handoff Events ═══[/]")
        console.print()
        _render_handoff_events(handoff_events)

        # Show current.md updates in log format
        git_dir = git.get_git_common_dir()
        handoff_dir = get_branch_handoff_dir(git_dir, branch)
        current_md = handoff_dir / "current.md"

        console.print("[bold]═══ Update Log (current.md) ═══[/]")
        console.print(f"  [dim]path[/]  {current_md}")
        console.print()

        if current_md.exists():
            content = current_md.read_text(encoding="utf-8")
            updates = _parse_updates_section(content)
            _render_updates_log(updates)

            # Show full content hint
            console.print("[dim]---[/]")
            console.print(f"[dim]Full file: {current_md}[/]")
            console.print("[dim]Use 'cat' or edit the file to see all sections[/]")
        else:
            console.print(
                "[dim]  (current.md not found — run `vibe3 handoff init` to create)[/]"
            )
        console.print()


@app.command()
def append(
    message: Annotated[str, typer.Argument(help="Message to append")],
    actor: Annotated[
        str,
        typer.Option(
            "--actor",
            "-a",
            help="Actor identifier (format: backend/model, e.g., codex/gpt-5.4)",
        ),
    ] = "unknown",
    kind: Annotated[
        str,
        typer.Option("--kind", "-k", help="Update kind (finding/blocker/next/note)"),
    ] = "note",
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
) -> None:
    """Append lightweight update to handoff file."""
    with _trace_scope(trace, "handoff append"):
        logger.bind(command="handoff append", actor=actor, kind=kind).info(
            "Appending handoff update"
        )

        service = HandoffService()
        handoff_path = service.append_current_handoff(message, actor, kind)

        console.print("[green]✓[/] Appended handoff update")
        console.print(f"  [dim]File: {handoff_path}[/]")


@app.command()
def plan(
    plan_ref: Annotated[str, typer.Argument(help="Plan document reference")],
    next_step: Annotated[
        str | None, typer.Option("--next-step", "-n", help="Next step suggestion")
    ] = None,
    blocked_by: Annotated[
        str | None, typer.Option("--blocked-by", "-b", help="Blocker description")
    ] = None,
    actor: Annotated[
        str,
        typer.Option(
            "--actor",
            "-a",
            help="Actor identifier (format: backend/model, e.g., codex/gpt-5.4)",
        ),
    ] = "unknown",
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
) -> None:
    """Record plan handoff."""
    _record_handoff_reference(
        command="handoff plan",
        ref_label="Plan",
        ref_value=plan_ref,
        next_step=next_step,
        blocked_by=blocked_by,
        actor=actor,
        trace=trace,
        method_name="record_plan",
    )


@app.command()
def report(
    report_ref: Annotated[str, typer.Argument(help="Report document reference")],
    next_step: Annotated[
        str | None, typer.Option("--next-step", "-n", help="Next step suggestion")
    ] = None,
    blocked_by: Annotated[
        str | None, typer.Option("--blocked-by", "-b", help="Blocker description")
    ] = None,
    actor: Annotated[
        str,
        typer.Option(
            "--actor",
            "-a",
            help="Actor identifier (format: backend/model, e.g., codex/gpt-5.4)",
        ),
    ] = "unknown",
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
) -> None:
    """Record report handoff."""
    _record_handoff_reference(
        command="handoff report",
        ref_label="Report",
        ref_value=report_ref,
        next_step=next_step,
        blocked_by=blocked_by,
        actor=actor,
        trace=trace,
        method_name="record_report",
    )


@app.command()
def audit(
    audit_ref: Annotated[str, typer.Argument(help="Audit document reference")],
    next_step: Annotated[
        str | None, typer.Option("--next-step", "-n", help="Next step suggestion")
    ] = None,
    blocked_by: Annotated[
        str | None, typer.Option("--blocked-by", "-b", help="Blocker description")
    ] = None,
    actor: Annotated[
        str,
        typer.Option(
            "--actor",
            "-a",
            help="Actor identifier (format: backend/model, e.g., codex/gpt-5.4)",
        ),
    ] = "unknown",
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
) -> None:
    """Record audit handoff."""
    _record_handoff_reference(
        command="handoff audit",
        ref_label="Audit",
        ref_value=audit_ref,
        next_step=next_step,
        blocked_by=blocked_by,
        actor=actor,
        trace=trace,
        method_name="record_audit",
    )
