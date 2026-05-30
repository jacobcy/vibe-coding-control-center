"""Internal system commands for Orchestra routing (hidden from users)."""

import json
from typing import Annotated

import typer

from vibe3.config import load_orchestra_config
from vibe3.services.issue_context_loader import load_issue_info

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

    dispatch_governance_execution(tick_count=tick, material_override=material)


@app.command("bootstrap")
def internal_bootstrap(
    issue: Annotated[int, typer.Argument(help="Issue number to bootstrap")],
    branch: Annotated[
        str,
        typer.Option("--branch", help="Target flow branch"),
    ],
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
        typer.Option("--dependency", help="Bind blocking dependency issue number"),
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
    from vibe3.clients.git_client import GitClient
    from vibe3.clients.github_client import GitHubClient
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.services.flow_orchestrator_service import FlowOrchestratorService

    config = load_orchestra_config()
    store = SQLiteClient()
    git = GitClient()
    github = GitHubClient()
    issue_info = load_issue_info(issue, config=config, github=github)
    service = FlowOrchestratorService(config, store=store, git=git, github=github)

    result = service.bootstrap_issue_flow(
        issue_info,
        branch=branch,
        slug=f"issue-{issue_info.number}",
        source=source,
        ensure_worktree=use_worktree,
        reactivate_existing=reactivate_existing,
        related_issue_numbers=tuple(related_issue_numbers or ()),
        dependency_issue_numbers=tuple(dependency_issue_numbers or ()),
    )
    typer.echo(json.dumps(result, indent=2, ensure_ascii=False, default=str))


@app.command("backfill-worktree-paths")
def backfill_worktree_paths() -> None:
    """Backfill worktree_path for existing active task/ flows."""
    from vibe3.clients.git_client import GitClient
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.services.status_query_service import is_auto_task_branch

    git = GitClient()
    store = SQLiteClient()

    worktrees = git.list_worktrees()
    backfilled_count = 0

    for wt_path, branch_ref in worktrees:
        branch = branch_ref.removeprefix("refs/heads/")
        if not is_auto_task_branch(branch):
            continue

        flow = store.get_flow_state(branch)
        if not flow:
            continue
        if flow.get("flow_status") != "active":
            continue
        if flow.get("worktree_path"):
            continue

        store.update_flow_state(branch, worktree_path=str(wt_path))
        backfilled_count += 1
        typer.echo(f"Backfilled {branch}: {wt_path}")

    typer.echo(f"\nBackfilled {backfilled_count} flows")
