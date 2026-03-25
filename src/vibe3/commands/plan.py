"""Plan command - Create implementation plans using codeagent-wrapper."""

from pathlib import Path
from typing import Annotated, Optional

import typer

from vibe3.clients.git_client import GitClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.commands.plan_helpers import run_plan
from vibe3.config.settings import VibeConfig
from vibe3.models.flow import MainBranchProtectedError
from vibe3.models.plan import PlanRequest, PlanScope
from vibe3.services.flow_service import FlowService
from vibe3.services.label_integration import transition_to_claimed
from vibe3.services.plan_context_builder import build_plan_context
from vibe3.utils.trace import enable_trace

app = typer.Typer(
    name="plan",
    help="Create implementation plans using codeagent-wrapper",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

_TRACE_OPT = Annotated[
    bool, typer.Option("--trace", help="Enable call tracing + DEBUG logs")
]
_DRY_RUN_OPT = Annotated[
    bool,
    typer.Option("--dry-run", help="Print command and prompt without executing"),
]
_AGENT_OPT = Annotated[
    Optional[str],
    typer.Option("--agent", help="Override agent preset (e.g., planner, planner-pro)"),
]
_BACKEND_OPT = Annotated[
    Optional[str],
    typer.Option("--backend", help="Override backend (claude, codex)"),
]
_MODEL_OPT = Annotated[
    Optional[str],
    typer.Option("--model", help="Override model (e.g., claude-3-opus)"),
]


@app.command()
def task(
    issue: Annotated[
        int | None,
        typer.Argument(help="Issue number (default: current flow's task issue)"),
    ] = None,
    instructions: Annotated[
        Optional[str],
        typer.Argument(help="Additional task guidance"),
    ] = None,
    trace: _TRACE_OPT = False,
    dry_run: _DRY_RUN_OPT = False,
    agent: _AGENT_OPT = None,
    backend: _BACKEND_OPT = None,
    model: _MODEL_OPT = None,
) -> None:
    """Create implementation plan for an issue.

    If no issue number is provided, uses the current flow's task issue.

    Examples:
        vibe3 plan task              # Use current flow's task issue
        vibe3 plan task 42           # Plan for issue #42
        vibe3 plan task 42 --dry-run
        vibe3 plan task 42 "Focus on security"
        vibe3 plan task 42 --agent planner-pro
    """
    if trace:
        enable_trace()

    config = VibeConfig.get_defaults()
    git = GitClient()
    branch = git.get_current_branch()

    # Auto-ensure flow for non-main branches
    flow_service = FlowService()
    try:
        flow_service.ensure_flow_for_branch(branch)
    except MainBranchProtectedError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    if issue is None:
        flow = flow_service.get_flow_status(branch)
        if not flow or not flow.task_issue_number:
            typer.echo(
                "Error: No issue number provided and current flow has no task issue.\n"
                "Use 'vibe3 plan task <issue>' or bind a task to the current flow.",
                err=True,
            )
            raise typer.Exit(1)
        issue = flow.task_issue_number
        typer.echo(f"-> Using flow task: Issue #{issue}")

    import typer as typer_module

    typer_module.echo(f"-> Plan: Issue #{issue}")

    scope = PlanScope.for_task(issue)
    request = PlanRequest(scope=scope)
    run_plan(  # type: ignore[call-arg]
        request,
        config,
        dry_run,
        instructions,
        agent,
        backend,
        model,
        build_plan_context,
    )

    if not dry_run:
        result = transition_to_claimed(issue)
        if not result.success and result.error and result.error != "no_issue_bound":
            typer.echo(
                f"Warning: Failed to transition issue state: {result.error}",
                err=True,
            )


@app.command()
def spec(
    file: Annotated[
        Optional[Path],
        typer.Option("--file", "-f", help="Path to spec file"),
    ] = None,
    msg: Annotated[
        Optional[str],
        typer.Option("--msg", help="Spec description"),
    ] = None,
    instructions: Annotated[
        Optional[str],
        typer.Argument(help="Additional task guidance"),
    ] = None,
    trace: _TRACE_OPT = False,
    dry_run: _DRY_RUN_OPT = False,
    agent: _AGENT_OPT = None,
    backend: _BACKEND_OPT = None,
    model: _MODEL_OPT = None,
) -> None:
    """Create implementation plan from a specification.

    Provide either --file or --msg (not both).

    Examples:
        vibe3 plan spec --file spec.md
        vibe3 plan spec --msg "Add dark mode support"
        vibe3 plan spec -f spec.md "Prioritize performance"
        vibe3 plan spec --msg "Refactor auth" --agent planner-pro
    """
    if trace:
        enable_trace()

    if file and msg:
        typer.echo("Error: Provide either --file or --msg, not both.", err=True)
        raise typer.Exit(1)

    if not file and not msg:
        typer.echo("Error: Provide either --file or --msg.", err=True)
        raise typer.Exit(1)

    config = VibeConfig.get_defaults()

    description = ""
    spec_path = None
    if file:
        if not file.exists():
            typer.echo(f"Error: File not found: {file}", err=True)
            raise typer.Exit(1)
        description = file.read_text(encoding="utf-8")
        spec_path = str(file.resolve())
        typer.echo(f"-> Plan from file: {file}")
    elif msg:
        description = msg
        typer.echo(f"-> Plan: {msg[:60]}{'...' if len(msg) > 60 else ''}")

    if spec_path and not dry_run:
        git = GitClient()
        store = SQLiteClient()
        try:
            branch = git.get_current_branch()
            store.update_flow_state(branch, spec_ref=spec_path)
            store.add_event(branch, "spec_bound", "user", detail=f"Spec bound: {file}")
        except Exception:
            pass

    scope = PlanScope.for_spec(description)
    request = PlanRequest(scope=scope)
    run_plan(  # type: ignore[call-arg]
        request,
        config,
        dry_run,
        instructions,
        agent,
        backend,
        model,
        build_plan_context,
    )
