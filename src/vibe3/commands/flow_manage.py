"""Flow management commands - update, bind, list-deleted, restore."""

import json
from typing import Annotated, List, Literal

import typer
from loguru import logger

from vibe3.commands.command_options import (
    FormatOption,
    TraceMinMsOption,
    TraceOption,
)
from vibe3.commands.common import enable_method_trace, validate_trace_options
from vibe3.models import IssueLink
from vibe3.services import FlowService, TaskService
from vibe3.ui import console, render_flow_created

# Type annotations for command arguments
BranchArg = Annotated[
    str | None,
    typer.Argument(help="Branch to update (defaults to current)"),
]
IssueArg = Annotated[
    str,
    typer.Argument(
        metavar="<issue-ref>",
        help="Issue reference(s) to bind as task/related/dependency",
    ),
]
TaskTailArg = Annotated[
    List[str] | None,
    typer.Argument(hidden=True),
]
SpecOption = Annotated[
    str | None,
    typer.Option(
        "--spec",
        help="Spec file path or issue reference. Use empty string '' to clear spec_ref",
    ),
]
ActorOption = Annotated[
    str | None,
    typer.Option(
        "--actor",
        "-a",
        help="Flow 默认署名（示例: codex/gpt-5.4）",
    ),
]
NameOption = Annotated[
    str | None,
    typer.Option(
        "--name",
        "-n",
        help="Flow 名称/Slug (默认从 branch 推断)",
    ),
]
StatusFilterOption = Annotated[
    Literal["active", "blocked", "done", "stale"] | None,
    typer.Option("--status", help="Filter by status"),
]
BindRoleOption = Annotated[
    Literal["task", "related", "dependency"],
    typer.Option("--role", help="Issue role (task, related, or dependency)"),
]
BindBranchOption = Annotated[
    str | None,
    typer.Option("--branch", help="Branch name (defaults to current branch)"),
]


def _merge_issue_refs(
    primary: str | None,
    tail: list[str] | None,
    *,
    primary_hint: str,
) -> str | list[str] | None:
    """Validate and merge issue refs from command arguments."""
    tail = tail or []
    if not tail:
        return primary
    if primary is None:
        raise ValueError(f"Additional issue refs require '{primary_hint}' prefix.")
    return [primary, *tail]


def _resolve_bind_branch(flow_service: FlowService, branch: str | None) -> str:
    """Resolve target branch for flow bind.

    For explicit --branch, require an existing non-protected flow branch.
    For implicit branch selection, preserve current behavior by using the
    current branch directly.
    """
    if branch is None:
        return str(flow_service.get_current_branch())

    if flow_service._is_main_branch(branch):
        typer.echo(
            f"Error: 受保护分支 '{branch}' 不能直接绑定 issue",
            err=True,
        )
        raise typer.Exit(1)

    if flow_service.get_flow_status(branch) is None:
        typer.echo(
            f"Error: 目标分支 '{branch}' 没有 flow\n"
            "先运行 `vibe3 flow update <branch>` 注册 flow，或切换到该分支后再执行绑定",
            err=True,
        )
        raise typer.Exit(1)

    return branch


def _ensure_branch_has_no_live_runtime_session(
    flow_service: FlowService, branch: str
) -> None:
    """Block flow mutations when branch has live runtime sessions."""
    from vibe3.agents import CodeagentBackend
    from vibe3.environment import SessionRegistryService

    backend = CodeagentBackend()
    registry = SessionRegistryService(store=flow_service.store, backend=backend)
    live = registry.get_truly_live_sessions_for_branch(branch)
    if live:
        typer.echo(
            f"Error: branch '{branch}' still has live runtime sessions; "
            "wait for the current automation run to finish before mutating flow state.",
            err=True,
        )
        raise typer.Exit(1)


def update(
    branch_arg: BranchArg = None,
    branch_opt: Annotated[
        str | None, typer.Option("--branch", help="Branch name or issue number")
    ] = None,
    name: NameOption = None,
    actor: ActorOption = None,
    spec: SpecOption = None,
    trace: TraceOption = False,
    min_ms: TraceMinMsOption = None,
    output_format: FormatOption = "table",
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="[DEPRECATED] Use --format json instead",
            hidden=True,
        ),
    ] = False,
) -> None:
    """Update flow metadata (idempotent add/update).

    If an issue number is provided (via positional arg or --branch option) and
    the corresponding branch doesn't exist in git, automatically creates the
    branch before registering flow.
    """
    validate_trace_options(trace, min_ms)
    if trace:
        enable_method_trace(min_ms=min_ms)

    branch = branch_opt or branch_arg
    # Handle deprecated --json flag
    if json_output and output_format == "table":
        typer.echo(
            "Warning: --json is deprecated, use --format json instead",
            err=True,
        )
        output_format = "json"
    from vibe3.clients import GitClient
    from vibe3.config import load_orchestra_config
    from vibe3.services import resolve_branch_arg
    from vibe3.utils import try_parse_issue_number

    target_branch = resolve_branch_arg(branch)

    # Auto-create branch if:
    # 1. Positional argument was an issue number (not explicit branch name)
    # 2. Target branch doesn't exist in git
    # 3. Target branch matches task/dev convention
    git = GitClient()
    issue_number_input = try_parse_issue_number(branch) if branch else None
    if issue_number_input is not None and not git.branch_exists(target_branch):
        # Create branch from scene_base_ref
        config = load_orchestra_config()
        logger.bind(
            command="flow update",
            branch=target_branch,
            issue_number=issue_number_input,
        ).info("Auto-creating branch for issue")

        git.create_branch_ref(target_branch, start_ref=config.scene_base_ref)
        if output_format == "table":
            typer.echo(
                f"✓ Created branch '{target_branch}' from {config.scene_base_ref}"
            )

    flow_service = FlowService()
    _ensure_branch_has_no_live_runtime_session(flow_service, target_branch)

    # Register/Ensure flow
    flow = flow_service.ensure_flow_for_branch(branch=target_branch, slug=name)

    # Update metadata if explicitly provided — keep name and actor separate
    # to avoid silently writing worktree identity when only --name is given.
    if name or actor:
        updates: dict[str, object] = {}
        if name:
            updates["flow_slug"] = name
        if actor:
            from vibe3.services import SignatureService

            updates["latest_actor"] = SignatureService.resolve_actor(
                explicit_actor=actor
            )
        if updates:
            flow_service.update_flow_metadata(target_branch, **updates)
        # Re-fetch flow state
        updated = flow_service.get_flow_status(target_branch)
        if updated:
            flow = updated

    if spec is not None:
        # spec provided (may be empty string to clear)
        if spec == "":
            # Clear spec_ref
            flow_service.store.update_flow_state(flow.branch, spec_ref=None)
        else:
            # Validate file path exists
            from pathlib import Path

            spec_path = Path(spec)
            if not spec_path.exists() or not spec_path.is_file():
                typer.echo(f"Error: Spec file not found: {spec}", err=True)
                typer.echo(
                    "Use a valid file path (e.g., docs/spec.md). "
                    "For issue binding, use 'vibe flow bind <issue> --role task'.",
                    err=True,
                )
                raise typer.Exit(1)
            # Bind spec (absolute path)
            flow_service.bind_spec(flow.branch, str(spec_path.resolve()), actor)

    if output_format in ("json", "yaml"):
        if output_format == "json":
            typer.echo(json.dumps(flow.model_dump(), indent=2, default=str))
        else:  # yaml
            import yaml

            typer.echo(
                yaml.dump(
                    flow.model_dump(), default_flow_style=False, allow_unicode=True
                )
            )
    else:
        render_flow_created(flow)


def bind(
    issue: IssueArg,
    issue_tail: TaskTailArg = None,
    branch: BindBranchOption = None,
    role: BindRoleOption = "task",
    trace: TraceOption = False,
    min_ms: TraceMinMsOption = None,
    output_format: FormatOption = "table",
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="[DEPRECATED] Use --format json instead",
            hidden=True,
        ),
    ] = False,
) -> None:
    """Bind issue(s) to a flow branch. (Usage: vibe flow bind <issue-ref>)"""
    validate_trace_options(trace, min_ms)
    if trace:
        enable_method_trace(min_ms=min_ms)

    # Handle deprecated --json flag
    if json_output and output_format == "table":
        typer.echo(
            "Warning: --json is deprecated, use --format json instead",
            err=True,
        )
        output_format = "json"
    from vibe3.utils import parse_issue_number

    issue_refs = _merge_issue_refs(issue, issue_tail, primary_hint="<issue>")
    if issue_refs is None:  # pragma: no cover - defensive
        raise typer.BadParameter("Missing issue reference")
    refs: List[str] = [issue_refs] if isinstance(issue_refs, str) else issue_refs
    logger.bind(command="flow bind", issue=issue_refs, role=role, branch=branch).info(
        "Binding issue to flow"
    )
    try:
        flow_service = FlowService()
        task_service = TaskService()
        target_branch = _resolve_bind_branch(flow_service, branch)
        _ensure_branch_has_no_live_runtime_session(flow_service, target_branch)

        links = []
        for ref in refs:
            issue_number = parse_issue_number(ref)

            if role == "dependency":
                # Compatibility path:
                # `flow bind --role dependency` no longer performs independent
                # dependency writes. It delegates to blocked dependency logic
                # for a single source of behavior.
                # Multi-ref compatibility remains ordered and per-ref:
                # each dependency delegates to `block_flow()` in sequence,
                # while the outward CLI output is synthesized from IssueLink.
                # With blocked_by accumulation fix, all dependency refs are
                # now accumulated in the issue body's blocked_by field.
                flow_service.block_flow(
                    target_branch, blocked_by_issue=issue_number, actor=None
                )
                links.append(
                    IssueLink(
                        branch=target_branch,
                        issue_number=issue_number,
                        issue_role="dependency",
                    )
                )
                continue

            # Create the persistent link in flow_issue_links (Source of Truth)
            link = task_service.link_issue(
                target_branch,
                issue_number,
                role,
                actor=None,
            )
            links.append(link)

        if output_format in ("json", "yaml"):
            output_data = (
                links[0].model_dump()
                if len(links) == 1
                else [link.model_dump() for link in links]
            )
            if output_format == "json":
                typer.echo(json.dumps(output_data, indent=2, default=str))
            else:  # yaml
                import yaml

                typer.echo(
                    yaml.dump(output_data, default_flow_style=False, allow_unicode=True)
                )
        else:
            for link in links:
                message = (
                    f"[green]✓[/] Issue #{link.issue_number} linked as {role} "
                    f"to flow {link.branch}"
                )
                console.print(message)
    except ValueError:
        logger.error(f"Invalid issue format: {issue_refs}")
        raise typer.BadParameter(f"Invalid issue format: {issue_refs}")


def list_deleted(
    output_format: FormatOption = "table",
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="[DEPRECATED] Use --format json instead",
            hidden=True,
        ),
    ] = False,
) -> None:
    """List all soft-deleted flows (for audit and recovery)."""
    # Handle deprecated --json flag
    if json_output and output_format == "table":
        typer.echo(
            "Warning: --json is deprecated, use --format json instead",
            err=True,
        )
        output_format = "json"
    from rich.table import Table

    from vibe3.clients import SQLiteClient

    store = SQLiteClient()
    deleted_flows = store.get_deleted_flows()

    if not deleted_flows:
        console.print("[yellow]No deleted flows found[/]")
        return

    if output_format in ("json", "yaml"):
        if output_format == "json":
            typer.echo(json.dumps(deleted_flows, indent=2, default=str))
        else:  # yaml
            import yaml

            typer.echo(
                yaml.dump(deleted_flows, default_flow_style=False, allow_unicode=True)
            )
    else:
        table = Table(title=f"Deleted Flows ({len(deleted_flows)} total)")
        table.add_column("Branch", style="cyan")
        table.add_column("Flow Slug", style="magenta")
        table.add_column("Status", style="yellow")
        table.add_column("Deleted At", style="red")

        for flow in deleted_flows:
            table.add_row(
                flow.get("branch", "?"),
                flow.get("flow_slug", "?"),
                flow.get("flow_status", "?"),
                flow.get("deleted_at", "?"),
            )

        console.print(table)
        console.print(
            "\n[dim]Use 'vibe flow restore <branch>' to recover a deleted flow[/]"
        )


def restore_flow(
    branch_arg: Annotated[
        str | None,
        typer.Argument(help="Branch name"),
    ] = None,
    branch_opt: Annotated[
        str | None, typer.Option("--branch", help="Branch name or issue number")
    ] = None,
    trace: TraceOption = False,
    min_ms: TraceMinMsOption = None,
) -> None:
    """Restore a soft-deleted flow."""
    validate_trace_options(trace, min_ms)
    if trace:
        enable_method_trace(min_ms=min_ms)

    branch = branch_opt or branch_arg
    if branch is None:
        typer.echo("Error: Branch is required for flow restore", err=True)
        raise typer.Exit(1)

    from vibe3.services import resolve_branch_arg

    target_branch = resolve_branch_arg(branch)

    from vibe3.clients import SQLiteClient

    store = SQLiteClient()

    # Check if flow exists
    flow = store.get_flow_state_include_deleted(target_branch)
    if flow is None:
        console.print(f"[red]Error: Flow '{target_branch}' not found[/]")
        raise typer.Exit(1)

    # Check if flow can be restored
    is_deleted = flow.get("deleted_at") is not None
    is_aborted = flow.get("flow_status") == "aborted"

    if not is_deleted and not is_aborted:
        console.print(f"[yellow]Flow '{target_branch}' is already active[/]")
        raise typer.Exit(0)

    # Restore the flow
    store.restore_flow(target_branch)
    console.print(f"[green]✓[/] Flow '{target_branch}' restored successfully")
    console.print(f"[dim]Run 'vibe flow show {target_branch}' to verify[/]")


def register_manage_commands(app: typer.Typer) -> None:
    """Register flow management commands."""
    app.command(name="update")(update)
    app.command()(bind)
    app.command(name="list-deleted")(list_deleted)
    app.command(name="restore")(restore_flow)
