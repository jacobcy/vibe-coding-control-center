"""Check command implementation."""

from typing import Annotated, Any, Literal

import typer
from rich.console import Console
from rich.markup import escape

from vibe3.commands.check_support import execute_check_mode, execute_remote_check
from vibe3.commands.common import enable_method_trace
from vibe3.observability import setup_logging
from vibe3.services import CheckService

app = typer.Typer(
    help="Verify handoff store consistency",
    rich_markup_mode="rich",
)


_console = Console()
_err_console = Console(stderr=True)


def _emit(line: str, *, err: bool = False) -> None:
    """Print a detail line, rendering Rich markup (typer.echo does not).

    ``typer.echo`` writes raw text, so inline tags like ``[green]`` would be
    printed literally (issue #2033). Routing through a Rich Console renders the
    markup as colour instead.
    """
    console = _err_console if err else _console
    console.print(line, highlight=False, soft_wrap=True)


def _emit_list(label: str, items: Any, *, style: str) -> None:
    """Emit a labelled, comma-joined list line (stdout) when non-empty.

    Interpolated values are escaped so branch names never inject markup.
    """
    values = [str(item) for item in (items or [])]
    if values:
        _emit(f"  [{style}]{label}[/{style}]: {escape(', '.join(values))}")


def _emit_failures(label: str, items: Any) -> None:
    """Emit one stderr line per failure (red) when any are present."""
    for failure in items or []:
        _emit(f"  [red]{label}[/red]: {escape(str(failure))}", err=True)


def _emit_agent_worktree_details(agent_worktrees: dict[str, Any]) -> None:
    """Render agent worktree cleanup details."""
    _emit_list("Agent worktrees cleaned", agent_worktrees.get("cleaned"), style="green")
    _emit_list(
        "Agent worktrees skipped (live)",
        agent_worktrees.get("skipped_live"),
        style="cyan",
    )
    _emit_failures("Agent worktrees failed", agent_worktrees.get("failed"))


def _emit_remote_branch_details(remote_branches: dict[str, Any]) -> None:
    """Render remote branch cleanup details."""
    _emit_list("Remote branches cleaned", remote_branches.get("cleaned"), style="green")
    _emit_list(
        "Remote branches skipped (protected)",
        remote_branches.get("skipped_protected"),
        style="dim",
    )
    _emit_list(
        "Remote branches skipped (open PR)",
        remote_branches.get("skipped_pr"),
        style="cyan",
    )
    _emit_failures("Remote branches failed", remote_branches.get("failed"))


def _emit_local_branch_details(local_branches: dict[str, Any]) -> None:
    """Render local branch cleanup details."""
    _emit_list("Local branches cleaned", local_branches.get("cleaned"), style="green")
    _emit_list(
        "Local branches skipped (protected)",
        local_branches.get("skipped_protected"),
        style="dim",
    )
    _emit_list(
        "Local branches skipped (current)",
        local_branches.get("skipped_current"),
        style="dim",
    )
    _emit_list(
        "Local branches skipped (active/blocked flow)",
        local_branches.get("skipped_active_flow"),
        style="dim",
    )
    _emit_list(
        "Local branches skipped (live)",
        local_branches.get("skipped_live"),
        style="cyan",
    )
    _emit_list(
        "Local worktrees removed",
        local_branches.get("skipped_worktree"),
        style="cyan",
    )
    _emit_failures("Local branches failed", local_branches.get("failed"))


def _emit_clean_branch_details(details: dict[str, Any]) -> None:
    """Render --clean-branch cleanup details with rendered Rich markup."""
    _emit_list("Cleaned", details.get("cleaned"), style="green")
    _emit_list("Removed invalid records", details.get("removed_invalid"), style="dim")
    _emit_failures("Failed", details.get("failed"))
    _emit_agent_worktree_details(details.get("agent_worktrees") or {})
    _emit_remote_branch_details(details.get("remote_branches") or {})
    _emit_local_branch_details(details.get("local_branches") or {})


def _emit_check_details(
    mode: Literal["init", "fix_all", "clean_branch", "branch"],
    details: dict[str, Any],
    *,
    fix_requested: bool,
) -> None:
    """Render mode-specific check details for CLI visibility.

    Uses a Rich Console so inline markup (e.g. ``[green]``) renders as colour
    instead of being printed literally (issue #2033).
    """
    if mode == "init":
        unresolvable = details.get("unresolvable") or []
        if unresolvable:
            _emit(
                f"  [yellow]Unresolvable[/yellow] ({len(unresolvable)} branches — "
                "no linked issues found in PR body):"
            )
            for branch in unresolvable:
                _emit(f"    {escape(str(branch))}")
        return

    if mode == "fix_all":
        fixed_count = details.get("fixed", 0)
        if fixed_count:
            _emit(f"  [green]Fixed[/green]: {fixed_count} flows")
        _emit_failures("Failed", details.get("failed"))
        return

    if mode == "clean_branch":
        _emit_clean_branch_details(details)
        return

    if mode == "branch":
        # Branch mode details are already in the summary
        return


@app.callback(invoke_without_command=True)
def check(
    ctx: typer.Context,
    init: Annotated[
        bool,
        typer.Option(
            "--init",
            help=(
                "Scan merged PRs on GitHub and back-fill missing task_issue_number "
                "for all flows. Requires network. Writes to local store. "
                "Safe to re-run (skips flows that already have task_issue_number)."
            ),
        ),
    ] = False,
    clean_branch: Annotated[
        bool,
        typer.Option(
            "--clean-branch",
            help=(
                "Clean residual resources: terminal flows, expired agent "
                "worktrees (>7d), expired remote branches (>7d), and local "
                "branches with no active/blocked flow record (>7d, merge "
                "status ignored)."
            ),
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help=(
                "With --clean-branch: bypass the 7-day age gate and delete "
                "every eligible branch (still skips active/blocked flows)."
            ),
        ),
    ] = False,
    branch: Annotated[
        str | None,
        typer.Option(
            "--branch",
            help="Check a single branch instead of all active flows.",
        ),
    ] = None,
    no_progress: Annotated[
        bool,
        typer.Option(
            "--no-progress",
            help="Disable progress bar for 'all' and 'fix_all' modes.",
        ),
    ] = False,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪（set VIBE3_TRACE=1）")
    ] = False,
    remote: Annotated[
        bool,
        typer.Option(
            "--remote",
            help="Audit remote GitHub issue label consistency.",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="With --remote: only report, don't modify labels."
        ),
    ] = False,
) -> None:
    """Verify handoff store consistency.

    Default mode: Check + fix all active flows.
    (Fixable: missing handoff file, missing pr_number, aborted status)

    [green]vibe3 check[/green]         Verify all flows + auto-fix

    [green]vibe3 check --init[/green]  Scan merged PRs + GitHub items,
                         back-fill task_issue_number for all flows.

    [green]vibe3 check --clean-branch[/green]  Clean residual branches:
                         terminal flows + branches with no active/blocked
                         flow record older than 7 days (merge status ignored).

    [green]vibe3 check --clean-branch --force[/green]  Also delete eligible
                         branches younger than 7 days (skips active/blocked).

    [green]vibe3 check --branch <name>[/green]  Verify a single branch
                         instead of all active flows.

    [green]vibe3 check --remote[/green]  Audit remote issue label consistency
                         (Rules 1-4). Use --dry-run to preview.
    """
    if trace:
        setup_logging(verbose=2)

    # Route --remote early (standalone mode, not combinable with local flags)
    if remote:
        _run_remote_check(dry_run=dry_run)
        return

    # Mutual exclusion check
    options_count = sum([init, clean_branch, branch is not None])
    if options_count > 1:
        typer.echo(
            "Error: --init, --clean-branch, and --branch are "
            "mutually exclusive options.",
            err=True,
        )
        raise typer.Exit(code=1)

    # Validate branch is non-empty when provided
    if branch is not None and not branch.strip():
        typer.echo("Error: --branch requires a non-empty branch name.", err=True)
        raise typer.Exit(code=1)

    if trace:
        enable_method_trace()

    try:
        service = CheckService()
        mode: Literal["init", "fix_all", "clean_branch", "branch"]
        if init:
            mode = "init"
            typer.echo("Scanning merged PRs to back-fill task_issue_number...")
        elif clean_branch:
            mode = "clean_branch"
            typer.echo("Checking for residual branches (done/aborted flows)...")

            # SAFETY CHECK: Require explicit confirmation for destructive operation
            # This prevents accidental cleanup of branches that might still be needed
            if not typer.confirm(
                "This will delete local/remote branches and worktrees. Continue?",
                default=False,
            ):
                typer.echo("Cleanup cancelled.", err=True)
                raise typer.Exit(code=0)
        elif branch:
            mode = "branch"
        else:
            mode = "fix_all"

        # Guard: --force only valid with --clean-branch
        if force and mode != "clean_branch":
            typer.echo(
                "Error: --force can only be used with --clean-branch.",
                err=True,
            )
            raise typer.Exit(code=1)

        result = execute_check_mode(
            service,
            mode,
            branch=branch,
            verbose=trace,
            show_progress=not no_progress,
            force=force,
        )

        if result.success:
            typer.echo(f"✓ {result.summary}")
            _emit_check_details(mode, result.details, fix_requested=True)
        else:
            typer.echo(f"✗ {result.summary}", err=True)
            _emit_check_details(mode, result.details, fix_requested=True)
            raise typer.Exit(code=1)

        # Hint for clean-branch after regular check
        if mode == "fix_all":
            Console().print(
                "\n  [dim]Hint: To clean residual branches for done/aborted flows, "
                "use 'vibe3 check --clean-branch'[/]"
            )
    finally:
        pass


def _run_remote_check(*, dry_run: bool) -> None:
    """Execute and display remote label audit results."""
    result = execute_remote_check(dry_run=dry_run)

    if result.issues_found == 0:
        typer.echo(f"检查 {result.total_issues} 个 issue，未发现问题。")
        return

    typer.echo(
        f"检查 {result.total_issues} 个 issue，"
        f"发现 {result.issues_found} 个问题：\n"
    )

    # Group by rule for display
    by_rule: dict[str, list[dict[str, object]]] = {}
    for r in result.results:
        rule = r["rules"]  # type: ignore[index]
        # If multiple rules matched, split and file under each
        for part in str(rule).split(", "):
            by_rule.setdefault(part, []).append(r)

    for rule_label, items in by_rule.items():
        typer.echo(f"{rule_label}:")
        for r in items:
            num = r["number"]  # type: ignore[index]
            rm = r["removed"]  # type: ignore[index]
            ad = r["added"]  # type: ignore[index]
            parts = []
            if rm:
                parts.append(f"移除 {', '.join(rm)}")  # type: ignore[arg-type]
            if ad:
                parts.append(f"添加 {', '.join(ad)}")  # type: ignore[arg-type]
            typer.echo(f"  - #{num}: {'，'.join(parts)}")
        typer.echo("")

    typer.echo(
        f"总计: 移除 {result.total_removed} 个标签，"
        f"添加 {result.total_added} 个标签"
    )

    if dry_run:
        typer.echo("\n[DRY RUN] 以上为预览，未实际修改标签")
