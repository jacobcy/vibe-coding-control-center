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
    from vibe3.execution.issue_role_sync_runner import run_issue_role_mode
    from vibe3.roles.manager import MANAGER_SYNC_SPEC

    run_issue_role_mode(
        issue_number=issue,
        dry_run=dry_run,
        async_mode=not no_async,
        fresh_session=fresh_session,
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
    from vibe3.execution.issue_role_sync_runner import run_issue_role_mode
    from vibe3.roles.supervisor import SUPERVISOR_CLI_SYNC_SPEC

    run_issue_role_mode(
        issue_number=issue,
        dry_run=dry_run,
        async_mode=not no_async,
        fresh_session=True,
        spec=SUPERVISOR_CLI_SYNC_SPEC,
    )
