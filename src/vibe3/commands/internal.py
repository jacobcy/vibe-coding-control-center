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
    dry_run: bool = False,
    no_async: Annotated[
        bool,
        typer.Option(
            "--no-async",
            help="Run synchronously (blocking) instead of async tmux session",
        ),
    ] = False,
    fresh_session: bool = False,
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
            dry_run=dry_run,
            fresh_session=fresh_session,
            show_prompt=False,
            spec=MANAGER_SYNC_SPEC,
        )
    else:
        run_issue_role_async(
            issue_number=issue,
            dry_run=dry_run,
            spec=MANAGER_SYNC_SPEC,
        )


@app.command("apply")
def internal_apply_dispatch(
    issue: Annotated[int, typer.Argument(help="Issue number to process")],
    dry_run: bool = False,
    no_async: Annotated[
        bool,
        typer.Option(
            "--no-async",
            help="Run synchronously (blocking) instead of async tmux session",
        ),
    ] = False,
) -> None:
    """L2: Dispatch the Supervisor/Apply agent for a governance issue."""
    from vibe3.execution.issue_role_sync_runner import (
        run_issue_role_async,
        run_issue_role_sync,
    )
    from vibe3.roles.supervisor import SUPERVISOR_CLI_SYNC_SPEC

    if no_async:
        run_issue_role_sync(
            issue_number=issue,
            dry_run=dry_run,
            fresh_session=True,
            show_prompt=False,
            spec=SUPERVISOR_CLI_SYNC_SPEC,
        )
    else:
        run_issue_role_async(
            issue_number=issue,
            dry_run=dry_run,
            spec=SUPERVISOR_CLI_SYNC_SPEC,
        )


@app.command("governance")
def internal_governance_dispatch(
    tick: Annotated[
        int, typer.Argument(help="Tick count for governance material rotation")
    ],
    dry_run: bool = False,
    show_prompt: bool = False,
) -> None:
    """L3: Dispatch the Governance scan agent.

    Governance scan uses tick count to rotate through supervisor materials.
    Unlike manager/apply, governance has no issue_number - it scans the whole system.

    Note: This command is only called via CLI self-invocation (internal governance)
    from the tmux wrapper launched by governance_scan handler. It always runs sync.
    """
    from vibe3.execution.governance_sync_runner import run_governance_sync

    # Governance always runs sync in CLI self-invocation context
    # (async wrapper already launched by governance_scan handler)
    run_governance_sync(
        tick_count=tick,
        dry_run=dry_run,
        show_prompt=show_prompt,
        session_id=None,
    )
