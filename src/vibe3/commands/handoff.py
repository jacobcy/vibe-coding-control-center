"""Handoff command implementation."""

from typing import Optional

import typer

from vibe3.services.handoff_service import HandoffService
from vibe3.ui.console import console

app = typer.Typer(help="Handoff management commands")


@app.command("init")
def handoff_init(
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Force overwrite if file exists",
    ),
) -> None:
    """Ensure shared current.md exists for current branch."""
    service = HandoffService()
    path = service.ensure_current_handoff(force=yes)
    console.print(f"[green]✓[/green] Handoff file ready: {path}")


@app.command("show")
def handoff_show() -> None:
    """Show shared current.md for current branch."""
    service = HandoffService()
    content = service.read_current_handoff()
    path = service._get_current_handoff_path()

    console.print(content)
    console.print()
    console.print(f"[dim]File path: {path}[/]")


@app.command("append")
def handoff_append(
    message: str = typer.Argument(..., help="Lightweight handoff update"),
    actor: str = typer.Option("unknown", help="Actor identifier"),
    kind: str = typer.Option("note", help="Update kind, e.g. finding/blocker/next"),
) -> None:
    """Append a lightweight update block to shared current.md."""
    service = HandoffService()
    path = service.append_current_handoff(message, actor, kind)
    console.print(f"[green]✓[/green] Appended handoff update: {path}")


@app.command("plan")
def handoff_plan(
    plan_ref: str = typer.Argument(..., help="Plan document reference"),
    next_step: Optional[str] = typer.Option(None, help="Next step suggestion"),
    blocked_by: Optional[str] = typer.Option(None, help="Blocker description"),
    actor: str = typer.Option("unknown", help="Actor identifier"),
) -> None:
    """Record plan handoff."""
    service = HandoffService()
    service.record_plan(plan_ref, next_step, blocked_by, actor)
    console.print(f"[green]✓[/green] Plan handoff recorded: {plan_ref}")


@app.command("report")
def handoff_report(
    report_ref: str = typer.Argument(..., help="Report document reference"),
    next_step: Optional[str] = typer.Option(None, help="Next step suggestion"),
    blocked_by: Optional[str] = typer.Option(None, help="Blocker description"),
    actor: str = typer.Option("unknown", help="Actor identifier"),
) -> None:
    """Record report handoff."""
    service = HandoffService()
    service.record_report(report_ref, next_step, blocked_by, actor)
    console.print(f"[green]✓[/green] Report handoff recorded: {report_ref}")


@app.command("audit")
def handoff_audit(
    audit_ref: str = typer.Argument(..., help="Audit document reference"),
    next_step: Optional[str] = typer.Option(None, help="Next step suggestion"),
    blocked_by: Optional[str] = typer.Option(None, help="Blocker description"),
    actor: str = typer.Option("unknown", help="Actor identifier"),
) -> None:
    """Record audit handoff."""
    service = HandoffService()
    service.record_audit(audit_ref, next_step, blocked_by, actor)
    console.print(f"[green]✓[/green] Audit handoff recorded: {audit_ref}")
