"""Flow analysis commands - sync-status, changes."""

import json
from typing import Annotated

import typer
from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.commands.command_options import FormatOption, TraceMinMsOption, TraceOption
from vibe3.commands.common import enable_method_trace, validate_trace_options
from vibe3.exceptions import GitError
from vibe3.ui.console import console


def sync_status(
    target: Annotated[
        str, typer.Option("--target", help="Target branch ref (default: main)")
    ] = "main",
    check_conflicts: Annotated[
        bool,
        typer.Option("--check-conflicts", help="Check for merge conflicts (slower)"),
    ] = False,
    output_format: FormatOption = "table",
    trace: TraceOption = False,
    min_ms: TraceMinMsOption = None,
) -> None:
    """Check sync status with remote target branch.

    Shows behind/ahead counts and lists new commits on target.
    Use --check-conflicts to detect potential merge conflicts (slower).

    Examples:
      vibe3 flow sync-status
      vibe3 flow sync-status --target dev
      vibe3 flow sync-status --check-conflicts
      vibe3 flow sync-status --format json
    """
    validate_trace_options(trace, min_ms)
    if trace:
        enable_method_trace(min_ms=min_ms)

    client = GitClient()
    remote_ref = f"origin/{target}"

    try:
        # Fetch target branch
        client.fetch(remote="origin", ref=target)
        logger.info(f"Fetched {remote_ref}")

        # Get behind count (commits on target not in HEAD)
        behind_output = client._run(["rev-list", f"HEAD..{remote_ref}", "--count"])
        behind = int(behind_output.strip()) if behind_output.strip() else 0

        # Get ahead count (commits on HEAD not in target)
        ahead_output = client._run(["rev-list", f"{remote_ref}..HEAD", "--count"])
        ahead = int(ahead_output.strip()) if ahead_output.strip() else 0

        # Get commit subjects for new commits on target
        new_commits = []
        if behind > 0:
            # Get SHAs and subjects for JSON output
            sha_output = client._run(
                ["log", f"HEAD..{remote_ref}", "--oneline", "--format=%h %s"]
            )

            for line in sha_output.splitlines():
                if line.strip():
                    parts = line.strip().split(" ", 1)
                    sha = parts[0]
                    subject = parts[1] if len(parts) > 1 else ""
                    new_commits.append({"sha": sha, "subject": subject})

        # Check for conflicts if requested
        conflict = False
        if check_conflicts:
            conflict = client.check_merge_conflicts(remote_ref)

        # Output
        if output_format == "json":
            output_data = {
                "behind": behind,
                "ahead": ahead,
                "conflict": conflict,
                "new_commits": new_commits,
            }
            typer.echo(json.dumps(output_data, indent=2))
        else:
            # Human-readable output
            console.print(f"[green]✓[/] Fetched {remote_ref}\n")

            console.print(f"Behind: {behind} commits")
            console.print(f"Ahead:  {ahead} commits")

            if check_conflicts:
                conflict_text = "[red]detected[/]" if conflict else "[green]none[/]"
                console.print(f"Conflicts: {conflict_text}")

            if behind > 0:
                console.print(f"\nNew commits on {remote_ref}:")
                for commit in new_commits:
                    console.print(f"  {commit['sha']} {commit['subject']}")

    except GitError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from e


def changes(
    output_format: FormatOption = "table",
    trace: TraceOption = False,
    min_ms: TraceMinMsOption = None,
) -> None:
    """Show working tree changes categorized by status.

    Displays staged, unstaged, and untracked files.
    Also checks for debug files (debug_*.py, debug_*.sh, tmp_*.py).

    Examples:
      vibe3 flow changes
      vibe3 flow changes --format json
    """
    validate_trace_options(trace, min_ms)
    if trace:
        enable_method_trace(min_ms=min_ms)

    client = GitClient()
    from pathlib import Path

    try:
        # Get porcelain status
        status_output = client._run(["status", "--porcelain"])

        # Parse into categories
        staged = []
        unstaged = []
        untracked = []

        for line in status_output.splitlines():
            if not line.strip():
                continue

            # Parse XY status codes
            # XY = two columns: X = staged status, Y = unstaged status
            # ' ' = no change, M = modified, A = added, D = deleted
            # R = renamed, C = copied, ? = untracked
            x = line[0] if len(line) > 0 else " "
            y = line[1] if len(line) > 1 else " "

            # Extract filename (skip the "XY " prefix)
            file = line[3:].strip() if len(line) > 3 else ""

            if not file:
                continue

            # Categorize based on XY codes
            # Simplified logic: staged if X != ' ' and X != '?'
            # unstaged if Y != ' ' and X != '?' and Y != '?'
            # untracked if XY == '??'
            if x == "?" and y == "?":
                untracked.append({"file": file, "status": "??"})
            else:
                if x != " " and x != "?":
                    staged.append({"file": file, "status": x})
                if y != " " and y != "?" and x != "?":
                    unstaged.append({"file": file, "status": y})

        # Get diff stat summaries
        staged_stat = ""
        unstaged_stat = ""

        if staged:
            staged_stat = client._run(["diff", "--cached", "--stat"])

        if unstaged:
            # For unstaged, we need to check if there are actual modifications
            # (not just untracked files marked in status)
            unstaged_stat = client._run(["diff", "--stat"])

        # Check for debug files
        repo_root = Path.cwd()
        debug_files = []

        for pattern in ["debug_*.py", "debug_*.sh", "tmp_*.py"]:
            for match in repo_root.glob(pattern):
                debug_files.append(match.name)

        # Output
        if output_format == "json":
            output_data = {
                "staged": staged,
                "unstaged": unstaged,
                "untracked": untracked,
                "debug_files": sorted(debug_files),
                "staged_stat": staged_stat,
                "unstaged_stat": unstaged_stat,
            }
            typer.echo(json.dumps(output_data, indent=2))
        else:
            # Human-readable output
            console.print(
                f"## Staged ({len(staged)} file{'s' if len(staged) != 1 else ''})"
            )
            if staged:
                # Show stat if available
                if staged_stat:
                    for line in staged_stat.splitlines():
                        console.print(f"  {line}")

            console.print(
                f"\n## Unstaged ({len(unstaged)} "
                f"file{'s' if len(unstaged) != 1 else ''})"
            )
            if unstaged:
                if unstaged_stat:
                    for line in unstaged_stat.splitlines():
                        console.print(f"  {line}")

            console.print(
                f"\n## Untracked ({len(untracked)} "
                f"file{'s' if len(untracked) != 1 else ''})"
            )

            if debug_files:
                console.print("\n[red]## Debug files found[/]")
                for debug_file in sorted(debug_files):
                    console.print(f"  {debug_file}   → should be removed")

    except GitError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from e


def register_analysis_commands(app: typer.Typer) -> None:
    """Register flow analysis commands."""
    app.command(name="sync-status")(sync_status)
    app.command(name="changes")(changes)
