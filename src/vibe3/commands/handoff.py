"""Handoff command - Agent chain and handoff events."""

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
from vibe3.ui.console import console

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
    for label, actor_label in [
        ("spec_ref", "planner_actor"),
        ("plan_ref", "planner_actor"),
        ("report_ref", "executor_actor"),
        ("audit_ref", "reviewer_actor"),
    ]:
        val = getattr(state, label, None)
        actor = getattr(state, actor_label, None) or ""
        actor_str = f"  [dim]{actor}[/]" if actor else ""
        status = val if val else "[dim](pending)[/]"
        console.print(f"  [dim]{label}[/]  {status}{actor_str}")
    console.print()


def _render_handoff_events(events: list[FlowEvent]) -> None:
    if not events:
        console.print("[dim]  no handoff events[/]")
        return

    for event in events:
        time_str = event.created_at[:16].replace("T", " ")
        actor_short = event.actor.split("/")[-1] if "/" in event.actor else event.actor
        console.print(
            f"[dim]{time_str}[/]  [magenta]{event.event_type}[/]  [dim]{actor_short}[/]"
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
def show(
    flow_name: Annotated[str | None, typer.Argument(help="Flow to show")] = None,
    show_all: Annotated[bool, typer.Option("--all", help="显示全部历史")] = False,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,  # noqa: E501
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
        limit = 0 if show_all else 5
        events_data = store.get_events(branch, limit=limit or 50)
        handoff_events = [
            FlowEvent(**e)
            for e in events_data
            if e.get("event_type", "").startswith("handoff_")
        ]

        if json_output:
            output = {
                "state": state.model_dump(),
                "events": [e.model_dump() for e in handoff_events],
            }
            typer.echo(json.dumps(output, indent=2, default=str))
            return

        console.print(f"\n[bold cyan]Handoff[/]: {state.flow_slug}")
        console.print()
        _render_agent_chain(state)
        console.print("[bold]═══ Recent Handoff Events ═══[/]")
        console.print()
        _render_handoff_events(handoff_events)
