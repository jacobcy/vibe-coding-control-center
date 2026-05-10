"""Internal system commands for Orchestra routing (hidden from users)."""

from typing import Annotated

import typer

app = typer.Typer(
    name="internal",
    help="Internal system commands for Orchestra routing (Do not use manually)",
    hidden=True,
    no_args_is_help=True,
)


@app.command("manager")
def internal_manager_dispatch(
    issue: Annotated[int, typer.Argument(help="Issue number to manage")],
    no_async: Annotated[
        bool,
        typer.Option(
            "--no-async",
            help="Run synchronously (blocking) instead of async tmux session",
        ),
    ] = False,
) -> None:
    """L3: Dispatch the State Manager agent."""
    from vibe3.execution.issue_role_sync_runner import (
        run_issue_role_async,
        run_issue_role_sync,
    )
    from vibe3.roles.manager import MANAGER_SYNC_SPEC

    if no_async:
        run_issue_role_sync(
            issue_number=issue,
            dry_run=False,  # Execution-only, no dry-run
            fresh_session=False,
            show_prompt=False,
            spec=MANAGER_SYNC_SPEC,
        )
    else:
        run_issue_role_async(
            issue_number=issue,
            dry_run=False,  # Execution-only, no dry-run
            spec=MANAGER_SYNC_SPEC,
        )


@app.command("apply")
def internal_apply_dispatch(
    issue: Annotated[int, typer.Argument(help="Issue number to process")],
    no_async: Annotated[
        bool,
        typer.Option(
            "--no-async",
            help="Run synchronously (blocking) instead of async tmux session",
        ),
    ] = False,
) -> None:
    """L2: Dispatch the Supervisor/Apply agent for a governance issue."""
    from vibe3.services.scan_service import dispatch_supervisor_execution

    dispatch_supervisor_execution(issue_number=issue, no_async=no_async)


@app.command("governance")
def internal_governance_dispatch(
    tick: Annotated[
        int, typer.Argument(help="Tick count for governance material rotation")
    ],
    material: Annotated[
        str | None,
        typer.Option(
            "--material",
            "-m",
            help="Override material rotation with specific governance role",
        ),
    ] = None,
) -> None:
    """L3: Dispatch the Governance scan agent (execution-only).

    Governance scan uses tick count to rotate through supervisor materials.
    Unlike manager/apply, governance has no issue_number - it scans the whole system.

    Note: This command is only called via CLI self-invocation (internal governance)
    from the tmux wrapper launched by governance_scan handler. It always runs sync.
    """
    from vibe3.services.scan_service import dispatch_governance_execution

    dispatch_governance_execution(material_override=material)
