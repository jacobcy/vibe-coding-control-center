"""Shared CLI option definitions for all agent commands."""

from typing import TYPE_CHECKING, Annotated, Optional

import typer

if TYPE_CHECKING:
    from vibe3.services.flow_service import FlowService

_TRACE_OPT = Annotated[
    bool, typer.Option("--trace", help="Enable call tracing + DEBUG logs")
]
_DRY_RUN_OPT = Annotated[
    bool, typer.Option("--dry-run", help="Print command without executing")
]
_ASYNC_OPT = Annotated[
    bool, typer.Option("--async", help="Run asynchronously in background")
]
_AGENT_OPT = Annotated[
    Optional[str], typer.Option("--agent", help="Override agent preset")
]
_BACKEND_OPT = Annotated[
    Optional[str], typer.Option("--backend", help="Override backend")
]
_MODEL_OPT = Annotated[Optional[str], typer.Option("--model", help="Override model")]
_WORKTREE_OPT = Annotated[
    bool,
    typer.Option(
        "--worktree",
        help="Pass --worktree to codeagent-wrapper (new isolated worktree execution)",
    ),
]


def ensure_flow_for_current_branch() -> tuple["FlowService", str]:
    """Auto-ensure flow for non-main branches.

    Returns:
        Tuple of (flow_service, branch_name)

    Raises:
        typer.Exit: If on main branch or flow creation fails
    """
    from vibe3.models.flow import MainBranchProtectedError
    from vibe3.services.flow_service import FlowService

    flow_service = FlowService()
    branch = flow_service.get_current_branch()

    try:
        flow_service.ensure_flow_for_branch(branch)
    except MainBranchProtectedError as e:
        typer.echo(f"Error: {e}\n", err=True)
        typer.echo("Tip: Create a feature branch first:", err=True)
        typer.echo("  git checkout -b <branch-name>", err=True)
        raise typer.Exit(1)

    return flow_service, branch
