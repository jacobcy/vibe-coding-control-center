"""Plan command - Create implementation plans using codeagent-wrapper."""

from pathlib import Path
from typing import Annotated, Optional

import typer

from vibe3.commands.command_options import (
    _AGENT_OPT,
    _BACKEND_OPT,
    _DRY_RUN_OPT,
    _MODEL_OPT,
    _TRACE_OPT,
    ensure_flow_for_current_branch,
)
from vibe3.config.settings import VibeConfig
from vibe3.models.plan import PlanRequest, PlanScope
from vibe3.services.codeagent_execution_service import (
    CodeagentExecutionService,
    create_codeagent_command,
)
from vibe3.services.flow_service import FlowService
from vibe3.services.label_integration import transition_to_claimed
from vibe3.services.plan_context_builder import build_plan_context
from vibe3.utils.trace import enable_trace

_ASYNC_OPT = Annotated[
    bool, typer.Option("--async", help="Run asynchronously in background")
]

app = typer.Typer(
    name="plan",
    help="Create implementation plans using codeagent-wrapper",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


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
    async_mode: _ASYNC_OPT = False,
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
        vibe3 plan task 42 --async   # Run in background
    """
    if trace:
        enable_trace()

    config = VibeConfig.get_defaults()
    flow_service, branch = ensure_flow_for_current_branch()

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

    typer.echo(f"-> Plan: Issue #{issue}")

    if async_mode and not dry_run:
        from vibe3.services.async_execution_service import AsyncExecutionService

        async_svc = AsyncExecutionService()
        cmd = ["python", "-m", "vibe3", "plan", "task", str(issue)]
        if instructions:
            cmd.append(instructions)
        if agent:
            cmd.extend(["--agent", agent])
        if backend:
            cmd.extend(["--backend", backend])
        if model:
            cmd.extend(["--model", model])
        cmd.append("--no-async")

        async_svc.start_async_execution("planner", cmd, branch)
        typer.echo("[green]✓[/] Plan started in background")
        typer.echo("Use 'vibe3 flow show' to check status")
        return

    scope = PlanScope.for_task(issue)
    request = PlanRequest(scope=scope)

    exec_svc = CodeagentExecutionService(config)
    command = create_codeagent_command(
        role="planner",
        context_builder=lambda: build_plan_context(request, config),
        task=instructions,
        dry_run=dry_run,
        handoff_kind="plan",
        agent=agent,
        backend=backend,
        model=model,
        config=config,
        branch=branch,
    )

    result = exec_svc.execute_sync(command)

    if not dry_run and result.success:
        label_result = transition_to_claimed(issue)
        if (
            not label_result.success
            and label_result.error
            and label_result.error != "no_issue_bound"
        ):
            typer.echo(
                f"Warning: Failed to transition issue state: {label_result.error}",
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
    async_mode: _ASYNC_OPT = False,
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
        vibe3 plan spec --file spec.md --async
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

    flow_service = FlowService()
    branch = flow_service.get_current_branch()

    if spec_path and not dry_run:
        try:
            flow_service.bind_spec(branch, spec_path, "user")
        except Exception:
            pass

    if async_mode and not dry_run:
        from vibe3.services.async_execution_service import AsyncExecutionService

        async_svc = AsyncExecutionService()
        cmd = ["python", "-m", "vibe3", "plan", "spec"]
        if file:
            cmd.extend(["--file", str(file)])
        elif msg:
            cmd.extend(["--msg", msg])
        if instructions:
            cmd.append(instructions)
        if agent:
            cmd.extend(["--agent", agent])
        if backend:
            cmd.extend(["--backend", backend])
        if model:
            cmd.extend(["--model", model])
        cmd.append("--no-async")

        async_svc.start_async_execution("planner", cmd, branch)
        typer.echo("[green]✓[/] Plan started in background")
        typer.echo("Use 'vibe3 flow show' to check status")
        return

    scope = PlanScope.for_spec(description)
    request = PlanRequest(scope=scope)

    exec_svc = CodeagentExecutionService(config)
    command = create_codeagent_command(
        role="planner",
        context_builder=lambda: build_plan_context(request, config),
        task=instructions,
        dry_run=dry_run,
        handoff_kind="plan",
        agent=agent,
        backend=backend,
        model=model,
        config=config,
        branch=branch,
    )

    exec_svc.execute_sync(command)
