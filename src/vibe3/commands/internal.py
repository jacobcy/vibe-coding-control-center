"""Internal system commands for Orchestra routing (hidden from users)."""

from typing import Annotated, Optional

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
    async_mode: bool = True,
    fresh_session: bool = False,
) -> None:
    """L3: Dispatch the State Manager agent."""
    from vibe3.manager.manager_run_service import run_manager_issue_mode

    run_manager_issue_mode(
        issue_number=issue,
        dry_run=dry_run,
        async_mode=async_mode,
        fresh_session=fresh_session,
    )


@app.command("apply")
def internal_apply_dispatch(
    supervisor: Annotated[str, typer.Argument(help="Supervisor handoff file")],
    issue: Annotated[
        Optional[int], typer.Option(help="Associated issue (optional)")
    ] = None,
    dry_run: bool = False,
    async_mode: bool = True,
) -> None:
    """L2: Dispatch the Supervisor/Apply agent."""
    from vibe3.orchestra.supervisor_run_service import run_supervisor_mode

    run_supervisor_mode(
        supervisor_file=supervisor,
        issue_number=issue,
        dry_run=dry_run,
        async_mode=async_mode,
    )
