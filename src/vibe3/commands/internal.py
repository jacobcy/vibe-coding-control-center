"""Internal system commands for Orchestra routing (hidden from users)."""

import json
from typing import Annotated

import typer

from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.exceptions import UserError
from vibe3.models.orchestration import IssueInfo

app = typer.Typer(
    name="internal",
    help="Internal system commands for Orchestra routing (Do not use manually)",
    hidden=True,
    no_args_is_help=True,
)


def _load_issue_info(issue_number: int) -> IssueInfo:
    """Load issue context for shared internal flow bootstrap."""
    from vibe3.clients.github_client import GitHubClient

    config = load_orchestra_config()
    github = GitHubClient()
    payload = github.view_issue(issue_number, repo=config.repo)
    if payload == "network_error":
        raise UserError(f"无法读取 issue #{issue_number}，请检查 GitHub 网络或认证状态")
    if payload is None or not isinstance(payload, dict):
        raise UserError(f"issue #{issue_number} 不存在或当前仓库不可访问")

    issue = IssueInfo.from_github_payload(payload)
    if issue is None:
        raise UserError(f"无法解析 issue #{issue_number} 的上下文")
    return issue


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

    dispatch_governance_execution(material_override=material)


@app.command("bootstrap-flow")
def internal_bootstrap_flow(
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
    issue_info = _load_issue_info(issue)
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
