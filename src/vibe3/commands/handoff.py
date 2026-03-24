"""Handoff command - Agent handoff chain and events."""

import json
from contextlib import contextmanager
from typing import Annotated, Iterator

import typer
from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.models.flow import FlowEvent, FlowState
from vibe3.observability.logger import setup_logging
from vibe3.observability.trace import trace_context
from vibe3.services.handoff_service import HandoffService
from vibe3.ui.console import console
from vibe3.utils.git_helpers import get_branch_handoff_dir

app = typer.Typer(
    help="Agent handoff chain and events",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


@contextmanager
def _noop() -> Iterator[None]:
    yield


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


@app.command()
def init(
    force: Annotated[bool, typer.Option("--yes", "-y", help="Force overwrite")] = False,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
) -> None:
    """Initialize handoff file for current branch."""
    if trace:
        setup_logging(verbose=2)

    ctx = trace_context(command="handoff init", domain="handoff") if trace else _noop()
    with ctx:
        logger.bind(command="handoff init", force=force).info("Initializing handoff")

        service = HandoffService()
        handoff_path = service.ensure_current_handoff(force=force)

        console.print(f"[green]✓[/] Handoff file ready: {handoff_path}")


@app.command()
def show(
    flow_name: Annotated[str | None, typer.Argument(help="Flow to show")] = None,
    show_all: Annotated[bool, typer.Option("--all", help="显示全部历史")] = False,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
) -> None:
    """Show agent handoff chain and events."""
    if trace:
        setup_logging(verbose=2)

    ctx = trace_context(command="handoff show", domain="handoff") if trace else _noop()
    with ctx:
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

        # Show current.md path and content
        git_dir = git.get_git_common_dir()
        handoff_dir = get_branch_handoff_dir(git_dir, branch)
        current_md = handoff_dir / "current.md"
        console.print("[bold]═══ Current Handoff ═══[/]")
        console.print(f"  [dim]path[/]  {current_md}")
        console.print()
        if current_md.exists():
            content = current_md.read_text(encoding="utf-8")
            console.print(content)
        else:
            console.print(
                "[dim]  (current.md not found — run `vibe3 handoff init` to create)[/]"
            )
        console.print()


@app.command()
def append(
    message: Annotated[str, typer.Argument(help="Message to append")],
    actor: Annotated[
        str, typer.Option("--actor", "-a", help="Actor identifier")
    ] = "claude",
    kind: Annotated[
        str,
        typer.Option("--kind", "-k", help="Update kind (finding/blocker/next/note)"),
    ] = "note",
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
) -> None:
    """Append lightweight update to handoff file."""
    if trace:
        setup_logging(verbose=2)

    ctx = (
        trace_context(command="handoff append", domain="handoff") if trace else _noop()
    )
    with ctx:
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
        str, typer.Option("--actor", "-a", help="Actor identifier")
    ] = "claude",
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
) -> None:
    """Record plan handoff."""
    if trace:
        setup_logging(verbose=2)

    ctx = trace_context(command="handoff plan", domain="handoff") if trace else _noop()
    with ctx:
        logger.bind(command="handoff plan", plan_ref=plan_ref, actor=actor).info(
            "Recording plan handoff"
        )

        service = HandoffService()
        service.record_plan(plan_ref, next_step, blocked_by, actor)

        console.print(f"[green]✓[/] Plan handoff recorded: {plan_ref}")


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
        str, typer.Option("--actor", "-a", help="Actor identifier")
    ] = "claude",
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
) -> None:
    """Record report handoff."""
    if trace:
        setup_logging(verbose=2)

    ctx = (
        trace_context(command="handoff report", domain="handoff") if trace else _noop()
    )
    with ctx:
        logger.bind(command="handoff report", report_ref=report_ref, actor=actor).info(
            "Recording report handoff"
        )

        service = HandoffService()
        service.record_report(report_ref, next_step, blocked_by, actor)

        console.print(f"[green]✓[/] Report handoff recorded: {report_ref}")


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
        str, typer.Option("--actor", "-a", help="Actor identifier")
    ] = "claude",
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
) -> None:
    """Record audit handoff."""
    if trace:
        setup_logging(verbose=2)

    ctx = trace_context(command="handoff audit", domain="handoff") if trace else _noop()
    with ctx:
        logger.bind(command="handoff audit", audit_ref=audit_ref, actor=actor).info(
            "Recording audit handoff"
        )

        service = HandoffService()
        service.record_audit(audit_ref, next_step, blocked_by, actor)

        console.print(f"[green]✓[/] Audit handoff recorded: {audit_ref}")
