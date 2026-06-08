"""Shared CLI option definitions for all agent commands."""

from typing import TYPE_CHECKING, Annotated, Literal, Optional

import typer

if TYPE_CHECKING:
    from vibe3.config import VibeConfig
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


def validate_show_prompt_dependency(dry_run: bool, show_prompt: bool) -> None:
    """Validate that --show-prompt is only used with --dry-run.

    Args:
        dry_run: Whether --dry-run flag is set
        show_prompt: Whether --show-prompt flag is set

    Raises:
        typer.Exit: If --show-prompt is used without --dry-run
    """
    if show_prompt and not dry_run:
        typer.echo("Error: --show-prompt requires --dry-run", err=True)
        raise typer.Exit(1)


def validate_model_backend_dependency(
    model: str | None,
    backend: str | None,
    config_backend: str | None = None,
) -> None:
    """Validate that --model requires backend (CLI or config).

    Args:
        model: The model specified via --model flag
        backend: The backend specified via --backend flag
        config_backend: The backend from runtime config

    Raises:
        typer.Exit: If --model is used without backend (CLI or config)
    """
    if model and not backend and not config_backend:
        typer.echo(
            "Error: --model requires --backend to be specified on CLI or in config.",
            err=True,
        )
        raise typer.Exit(1)


def load_config_and_validate_model(
    role: str,
    agent: str | None,
    backend: str | None,
    model: str | None,
) -> "VibeConfig":
    """Load runtime config and validate --model requires backend.

    Combines config loading with model-backend validation into a single step.
    Extracts config_backend with defensive getattr to handle malformed configs.

    Args:
        role: Role name (run/plan/review)
        agent: CLI --agent value
        backend: CLI --backend value
        model: CLI --model value

    Returns:
        Loaded VibeConfig

    Raises:
        typer.Exit: If config loading fails or --model used without backend
        ConfigError: If config loading fails
    """
    from vibe3.config import load_runtime_config
    from vibe3.config.cli_overrides import build_role_cli_overrides
    from vibe3.exceptions import ConfigError

    cli_overrides = build_role_cli_overrides(role, agent, backend, model)
    try:
        config = load_runtime_config(cli_overrides=cli_overrides or None)
    except ConfigError as e:
        typer.echo(f"Configuration error: {e}", err=True)
        raise typer.Exit(1) from e

    role_config = getattr(config, role, None)
    agent_config = getattr(role_config, "agent_config", None) if role_config else None
    config_backend = agent_config.backend if agent_config else None
    validate_model_backend_dependency(model, backend, config_backend)

    return config


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
