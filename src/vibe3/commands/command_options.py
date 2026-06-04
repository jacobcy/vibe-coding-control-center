"""Shared CLI option definitions for all agent commands."""

from typing import TYPE_CHECKING, Annotated, Literal, Optional

import typer

if TYPE_CHECKING:
    from vibe3.services.flow_service import FlowService

_TRACE_OPT = Annotated[
    bool, typer.Option("--trace", help="Enable call tracing (set VIBE3_TRACE=1)")
]
_DRY_RUN_OPT = Annotated[
    bool, typer.Option("--dry-run", help="Print command without executing")
]
_SHOW_PROMPT_OPT = Annotated[
    bool,
    typer.Option(
        "--show-prompt",
        help=(
            "With --dry-run, print the full rendered prompt "
            "in addition to the summary"
        ),
    ),
]
_ASYNC_OPT = Annotated[
    bool,
    typer.Option(
        "--no-async",
        help="Run synchronously (blocking) instead of async tmux session",
    ),
]
_AGENT_OPT = Annotated[
    Optional[str], typer.Option("--agent", help="Override agent preset")
]
_BACKEND_OPT = Annotated[
    Optional[str], typer.Option("--backend", help="Override backend")
]
_MODEL_OPT = Annotated[Optional[str], typer.Option("--model", help="Override model")]
_FRESH_SESSION_OPT = Annotated[
    bool,
    typer.Option(
        "--fresh-session",
        help="Skip session resume and start a fresh agent session",
    ),
]

# Output format options
AllOption = Annotated[
    bool,
    typer.Option("--all", help="Include all items (not just active)"),
]

FormatOption = Annotated[
    Literal["json", "yaml", "table"],
    typer.Option("--format", help="Output format: json, yaml, or table"),
]

RemoteOption = Annotated[
    bool,
    typer.Option("--remote", help="Fetch complete remote state from GitHub"),
]

VerboseOption = Annotated[
    bool,
    typer.Option("--verbose", "-v", help="Show full details"),
]

ActorFilterOption = Annotated[
    str | None,
    typer.Option("--actor", help="Filter by actor pattern"),
]

TraceOption = Annotated[
    bool,
    typer.Option("--trace", help="Enable call tracing (set VIBE3_TRACE=1)"),
]

TraceMinMsOption = Annotated[
    float | None,
    typer.Option(
        "--min-ms",
        min=0.0,
        help="Min duration (ms) to show in trace (use with --trace)",
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


def build_role_cli_overrides(
    role: str,
    agent: str | None,
    backend: str | None,
    model: str | None,
) -> dict[str, str]:
    """Build cli_overrides dict for load_runtime_config.

    Args:
        role: Role name ("plan", "review", or "run")
        agent: Agent override (optional)
        backend: Backend override (optional)
        model: Model override (optional)

    Returns:
        Dict of config key -> value for load_runtime_config
    """
    overrides: dict[str, str] = {}
    if backend:
        overrides[f"{role}.agent_config.backend"] = backend
    if model:
        overrides[f"{role}.agent_config.model"] = model
    if agent:
        overrides[f"{role}.agent_config.agent"] = agent
    return overrides
