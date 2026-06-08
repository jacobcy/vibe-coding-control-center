"""Output formatting helpers for check command."""

from __future__ import annotations

from typing import Any, Literal

from rich.console import Console
from rich.markup import escape

_console = Console()
_err_console = Console(stderr=True)


def emit_line(line: str, *, err: bool = False) -> None:
    """Print a detail line, rendering Rich markup (typer.echo does not).

    ``typer.echo`` writes raw text, so inline tags like ``[green]`` would be
    printed literally (issue #2033). Routing through a Rich Console renders the
    markup as colour instead.
    """
    console = _err_console if err else _console
    console.print(line, highlight=False, soft_wrap=True)


def emit_list(label: str, items: Any, *, style: str) -> None:
    """Emit a labelled, comma-joined list line (stdout) when non-empty.

    Interpolated values are escaped so branch names never inject markup.
    """
    values = [str(item) for item in (items or [])]
    if values:
        emit_line(f"  [{style}]{label}[/{style}]: {escape(', '.join(values))}")


def emit_failures(label: str, items: Any) -> None:
    """Emit one stderr line per failure (red) when any are present."""
    for failure in items or []:
        emit_line(f"  [red]{label}[/red]: {escape(str(failure))}", err=True)


def emit_agent_worktree_details(agent_worktrees: dict[str, Any]) -> None:
    """Render agent worktree cleanup details."""
    emit_list("Agent worktrees cleaned", agent_worktrees.get("cleaned"), style="green")
    emit_list(
        "Agent worktrees skipped (live)",
        agent_worktrees.get("skipped_live"),
        style="cyan",
    )
    emit_failures("Agent worktrees failed", agent_worktrees.get("failed"))


def emit_remote_branch_details(remote_branches: dict[str, Any]) -> None:
    """Render remote branch cleanup details."""
    emit_list("Remote branches cleaned", remote_branches.get("cleaned"), style="green")
    emit_list(
        "Remote branches skipped (protected)",
        remote_branches.get("skipped_protected"),
        style="dim",
    )
    emit_list(
        "Remote branches skipped (open PR)",
        remote_branches.get("skipped_pr"),
        style="cyan",
    )
    emit_failures("Remote branches failed", remote_branches.get("failed"))


def emit_local_branch_details(local_branches: dict[str, Any]) -> None:
    """Render local branch cleanup details."""
    emit_list("Local branches cleaned", local_branches.get("cleaned"), style="green")
    emit_list(
        "Local branches skipped (protected)",
        local_branches.get("skipped_protected"),
        style="dim",
    )
    emit_list(
        "Local branches skipped (current)",
        local_branches.get("skipped_current"),
        style="dim",
    )
    emit_list(
        "Local branches skipped (active/blocked flow)",
        local_branches.get("skipped_active_flow"),
        style="dim",
    )
    emit_list(
        "Local branches skipped (live)",
        local_branches.get("skipped_live"),
        style="cyan",
    )
    emit_list(
        "Local worktrees removed",
        local_branches.get("skipped_worktree"),
        style="cyan",
    )
    emit_failures("Local branches failed", local_branches.get("failed"))


def emit_clean_branch_details(details: dict[str, Any]) -> None:
    """Render --clean-branch cleanup details with rendered Rich markup."""
    emit_list("Cleaned", details.get("cleaned"), style="green")
    emit_list("Removed invalid records", details.get("removed_invalid"), style="dim")
    emit_failures("Failed", details.get("failed"))
    emit_agent_worktree_details(details.get("agent_worktrees") or {})
    emit_remote_branch_details(details.get("remote_branches") or {})
    emit_local_branch_details(details.get("local_branches") or {})


def emit_check_details(
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
            emit_line(
                f"  [yellow]Unresolvable[/yellow] ({len(unresolvable)} branches — "
                "no linked issues found in PR body):"
            )
            for branch in unresolvable:
                emit_line(f"    {escape(str(branch))}")
        return

    if mode == "fix_all":
        fixed_count = details.get("fixed", 0)
        if fixed_count:
            emit_line(f"  [green]Fixed[/green]: {fixed_count} flows")
        emit_failures("Failed", details.get("failed"))
        return

    if mode == "clean_branch":
        emit_clean_branch_details(details)
        return

    if mode == "branch":
        # Branch mode details are already in the summary
        return
