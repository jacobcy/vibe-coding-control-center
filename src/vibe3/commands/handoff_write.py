"""Handoff write commands - Modify handoff state and record events."""

from typing import Annotated

import typer
from loguru import logger

from vibe3.commands.common import trace_scope
from vibe3.services.handoff_service import HandoffService
from vibe3.ui.console import console


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
    with trace_scope(trace, command, domain="handoff"):
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


def init(
    force: Annotated[bool, typer.Option("--yes", "-y", help="Force overwrite")] = False,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
) -> None:
    """Initialize handoff file for current branch."""
    with trace_scope(trace, "handoff init", domain="handoff"):
        logger.bind(command="handoff init", force=force).info("Initializing handoff")

        service = HandoffService()
        handoff_path = service.ensure_current_handoff(force=force)

        console.print(f"[green]✓[/] Handoff file ready: {handoff_path}")


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
    with trace_scope(trace, "handoff append", domain="handoff"):
        logger.bind(command="handoff append", actor=actor, kind=kind).info(
            "Appending handoff update"
        )

        service = HandoffService()
        handoff_path = service.append_current_handoff(message, actor, kind)

        console.print("[green]✓[/] Appended handoff update")
        console.print(f"  [dim]File: {handoff_path}[/]")


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
