"""Internal system commands for Orchestra routing (hidden from users)."""

import json
import logging
import os
from typing import Annotated

import typer

from vibe3.commands.command_options import (
    _ASYNC_OPT,
    _DRY_RUN_OPT,
    _SHOW_PROMPT_OPT,
    validate_show_prompt_dependency,
)
from vibe3.config import load_orchestra_config
from vibe3.services.issue import load_issue_info

logger = logging.getLogger(__name__)


def _require_async_child(yes: bool = False) -> None:
    """Guard: ensure internal commands are called from async child context.

    When VIBE3_ASYNC_CHILD is not set, this is a direct invocation (not from
    tmux wrapper). Emit a warning; abort unless --yes is given.

    Args:
        yes: If True, allow direct invocation despite missing marker.
    """
    if os.environ.get("VIBE3_ASYNC_CHILD") == "1":
        return
    logger.warning(
        "vibe3 internal commands are intended for async child execution only. "
        "External dispatch should use event entry points (DomainEvent). "
        "Pass --yes to override."
    )
    if not yes:
        raise typer.Exit(code=1)


app = typer.Typer(
    name="internal",
    help="Internal system commands for Orchestra routing (Do not use manually)",
    hidden=True,
    no_args_is_help=True,
)


@app.command("manager")
def internal_manager_dispatch(
    issue: Annotated[
        int | None,
        typer.Argument(
            help="Issue number to manage (optional, defaults to current flow)"
        ),
    ] = None,
    no_async: _ASYNC_OPT = False,
    dry_run: _DRY_RUN_OPT = False,
    show_prompt: _SHOW_PROMPT_OPT = False,
    branch: Annotated[
        str | None,
        typer.Option("--branch", help="Branch name or issue number"),
    ] = None,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Bypass async child guard (for debugging)"),
    ] = False,
) -> None:
    """L3: Dispatch the State Manager agent.

    If issue is not specified, uses the issue bound to current branch/flow.
    """
    _require_async_child(yes=yes)

    # Validate --show-prompt requires --dry-run
    validate_show_prompt_dependency(dry_run, show_prompt)

    # --show-prompt requires sync execution (async path lacks show_prompt support)
    if show_prompt:
        no_async = True

    # Resolve issue number from current flow if not specified
    if issue is None:
        from vibe3.services.flow import FlowService

        flow_service = FlowService()
        current_branch = branch or flow_service.get_current_branch()

        if not current_branch:
            typer.echo(
                "Error: No current branch detected.\n"
                "Please specify an issue: vibe3 internal manager <issue>\n"
                "Or checkout a branch first.",
                err=True,
            )
            raise typer.Exit(1)

        flow = flow_service.get_flow_status(current_branch)

        if not flow:
            typer.echo(
                f"Error: No flow found for branch '{current_branch}'.\n"
                f"Options:\n"
                f"  1. Bind an issue: vibe3 flow bind <issue>\n"
                f"  2. Specify issue: vibe3 internal manager <issue>",
                err=True,
            )
            raise typer.Exit(1)

        if not flow.task_issue_number:
            typer.echo(
                f"Error: Flow on branch '{current_branch}' has no bound issue.\n"
                f"Options:\n"
                f"  1. Bind an issue: vibe3 flow bind <issue>\n"
                f"  2. Specify issue: vibe3 internal manager <issue>",
                err=True,
            )
            raise typer.Exit(1)

        issue = flow.task_issue_number
        logger.info(
            f"Using issue #{issue} from current flow (branch: {current_branch})"
        )

    from vibe3.execution import (
        run_issue_role_async,
        run_issue_role_sync,
    )
    from vibe3.roles import MANAGER_SYNC_SPEC

    if no_async:
        run_issue_role_sync(
            issue_number=issue,
            dry_run=dry_run,
            fresh_session=False,
            show_prompt=show_prompt,
            spec=MANAGER_SYNC_SPEC,
            branch=branch,
        )
    else:
        run_issue_role_async(
            issue_number=issue,
            dry_run=dry_run,
            spec=MANAGER_SYNC_SPEC,
            branch=branch,
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
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Bypass async child guard (for debugging)"),
    ] = False,
) -> None:
    """L2: Dispatch the Supervisor/Apply agent for a governance issue."""
    _require_async_child(yes=yes)

    from vibe3.roles import dispatch_supervisor_execution

    dispatch_supervisor_execution(issue_number=issue, no_async=no_async)


@app.command("governance")
def internal_governance_dispatch(
    tick: Annotated[
        int, typer.Argument(help="Tick count for governance material rotation")
    ],
    execution_count: Annotated[
        int,
        typer.Argument(help="Independent execution count for material rotation"),
    ] = 0,
    material: Annotated[
        str | None,
        typer.Option(
            "--material",
            "-m",
            help="Override material rotation with specific governance role",
        ),
    ] = None,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Bypass async child guard (for debugging)"),
    ] = False,
) -> None:
    """L3: Dispatch the Governance scan agent (execution-only).

    Governance scan uses tick count to rotate through supervisor materials.
    Unlike manager/apply, governance has no issue_number - it scans the whole system.

    Note: This command is only called via CLI self-invocation (internal governance)
    from the tmux wrapper launched by governance_scan handler. It always runs sync.
    """
    _require_async_child(yes=yes)

    from vibe3.roles import dispatch_governance_execution

    dispatch_governance_execution(
        tick_count=tick, execution_count=execution_count, material_override=material
    )


@app.command("bootstrap")
def internal_bootstrap(
    issue: Annotated[int, typer.Argument(help="Issue number to bootstrap")],
    branch: Annotated[
        str | None,
        typer.Option(
            "--branch",
            help="Target flow branch (defaults to dev/issue-<id>)",
        ),
    ] = None,
    use_worktree: Annotated[
        bool,
        typer.Option(
            "--worktree",
            help="Resolve or create worktree context for the target branch",
        ),
    ] = False,
    related_issue_numbers: Annotated[
        list[int] | None,
        typer.Option("--related", help="Bind additional related issue number"),
    ] = None,
    dependency_issue_numbers: Annotated[
        list[int] | None,
        typer.Option(
            "--blocked-by",
            "--dependency",
            help="Bind blocking dependency issue number",
        ),
    ] = None,
    blocked_reason: Annotated[
        str | None,
        typer.Option("--blocked-reason", help="Reason this flow is blocked"),
    ] = None,
    source: Annotated[
        str,
        typer.Option("--source", help="Bootstrap source label"),
    ] = "skill",
    reactivate_existing: Annotated[
        bool,
        typer.Option(
            "--reactivate-existing",
            help="Reactivate existing flow instead of creating a new one",
        ),
    ] = False,
) -> None:
    """Bootstrap a standardized flow scene through the shared service path."""
    from vibe3.clients import GitClient, GitHubClient, SQLiteClient
    from vibe3.services.orchestra import FlowOrchestratorService

    if dependency_issue_numbers and blocked_reason is not None:
        typer.echo(
            "Error: 不能同时指定 --blocked-reason 与 --blocked-by/--dependency",
            err=True,
        )
        raise typer.Exit(1)

    config = load_orchestra_config()
    store = SQLiteClient()
    git = GitClient()
    github = GitHubClient()
    issue_info = load_issue_info(issue, config=config, github=github)
    service = FlowOrchestratorService(config, store=store, git=git, github=github)

    # When --branch is not specified, auto-create a dev/issue-<id>
    # human-collaboration branch (orchestra always passes explicit --branch)
    resolved_branch = branch or f"dev/issue-{issue_info.number}"

    result = service.bootstrap_issue_flow(
        issue_info,
        branch=resolved_branch,
        slug=f"issue-{issue_info.number}",
        source=source,
        actor="system:bootstrap",
        ensure_worktree=use_worktree,
        reactivate_existing=reactivate_existing,
        related_issue_numbers=tuple(related_issue_numbers or ()),
        dependency_issue_numbers=tuple(dependency_issue_numbers or ()),
        blocked_reason=blocked_reason,
    )

    # Ensure handoff exists using shared helper (quiet, preserves JSON output)
    from vibe3.commands.flow_manage import ensure_current_handoff_for_flow

    try:
        ensure_current_handoff_for_flow(resolved_branch, source="bootstrap")
    except Exception as e:
        # Non-critical failure: log and continue
        logger.warning(f"Failed to initialize handoff: {e}")

    typer.echo(json.dumps(result, indent=2, ensure_ascii=False, default=str))
