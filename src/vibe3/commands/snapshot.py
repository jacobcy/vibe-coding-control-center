"""Snapshot command - 代码库结构快照管理."""

import json
from typing import Annotated

import typer

from vibe3.analysis import snapshot_service
from vibe3.analysis.snapshot_diff import compute_diff
from vibe3.utils.trace import enable_trace

app = typer.Typer(
    name="snapshot",
    help="""Project-level structure tracking (persistent).

When to use snapshot:
  - Tracking project structure evolution (save points)
  - Comparing structure vs baseline / branches
  - Finding structural changes (module, dependency, LOC growth)

Subcommands:
  build                     Build current structure (memory only)
  save [--as-baseline]      Persist structure (use --as-baseline for diff)
  list                      List all saved snapshots
  show [<snapshot-id>]      Show structure details
  diff [<snapshot-id>]      Compare structure vs baseline

For single-file analysis → use:
  vibe3 inspect              (real-time file & change analysis)

Examples:
  vibe3 snapshot save --as-baseline    # Save as branch baseline
  vibe3 snapshot diff                  # Compare with branch baseline
  vibe3 snapshot diff latest           # Compare with latest snapshot
  vibe3 snapshot show --branch main    # Show baseline for 'main' branch""",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

_JSON_OPT = Annotated[bool, typer.Option("--json", help="Output as JSON")]
_TRACE_OPT = Annotated[
    bool, typer.Option("--trace", help="Enable call tracing + DEBUG logs")
]


@app.command()
def build(
    json_out: _JSON_OPT = False,
    trace: _TRACE_OPT = False,
) -> None:
    """Build a structure snapshot from current codebase (in-memory, not saved).

    The snapshot captures:
    - File structure (LOC, functions, dependencies)
    - Module aggregation
    - Dependency graph
    - Quality metrics

    This command only builds the snapshot in memory. Use `snapshot save` to persist.

    Examples:
        vibe3 snapshot build
        vibe3 snapshot build --json
    """
    if trace:
        enable_trace()

    try:
        snapshot = snapshot_service.build_snapshot()

        if json_out:
            typer.echo(snapshot.model_dump_json(indent=2))
        else:
            typer.echo(f"✓ Snapshot built: {snapshot.snapshot_id}")
            typer.echo(f"  Branch: {snapshot.branch}")
            typer.echo(f"  Commit: {snapshot.commit_short}")
            typer.echo(f"  Files: {snapshot.metrics.total_files}")
            typer.echo(f"  Total LOC: {snapshot.metrics.total_loc}")
            typer.echo(f"  Functions: {snapshot.metrics.total_functions}")
            typer.echo(
                "\n  [yellow]Tip:[/yellow] "
                "Use `snapshot save` to persist this snapshot"
            )
    except snapshot_service.SnapshotError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def save(
    as_baseline: Annotated[
        bool,
        typer.Option("--as-baseline", help="Save as branch baseline for diff"),
    ] = False,
    json_out: _JSON_OPT = False,
    trace: _TRACE_OPT = False,
) -> None:
    """Build and persist a structure snapshot from current codebase.

    This is the canonical command for creating and saving a snapshot to disk.

    Use --as-baseline to save as the branch's baseline for `snapshot diff`.
    This is automatically called at development start points (vibe-new, state/claimed).

    Examples:
        vibe3 snapshot save
        vibe3 snapshot save --as-baseline
        vibe3 snapshot save --json
    """
    from vibe3.clients.git_client import GitClient

    if trace:
        enable_trace()

    try:
        if as_baseline:
            # Save as branch baseline (for diff workflow)
            git = GitClient()
            current_branch = git.get_current_branch()
            filepath = snapshot_service.save_branch_baseline(current_branch)
            if filepath is None:
                typer.echo("Error: Failed to save baseline", err=True)
                raise typer.Exit(1)
            snapshot = snapshot_service.load_branch_baseline(current_branch)
            if snapshot is None:
                typer.echo("Error: Saved baseline could not be loaded", err=True)
                raise typer.Exit(1)
            action = "saved as baseline"
        else:
            # Save regular snapshot
            snapshot = snapshot_service.build_snapshot()
            filepath = snapshot_service.save_snapshot(snapshot)
            action = "saved"

        if json_out:
            typer.echo(snapshot.model_dump_json(indent=2))
        else:
            typer.echo(f"✓ Snapshot {action}: {snapshot.snapshot_id}")
            typer.echo(f"  Branch: {snapshot.branch}")
            typer.echo(f"  Commit: {snapshot.commit_short}")
            typer.echo(f"  Files: {snapshot.metrics.total_files}")
            typer.echo(f"  Total LOC: {snapshot.metrics.total_loc}")
            typer.echo(f"  Functions: {snapshot.metrics.total_functions}")
            typer.echo(f"  Saved to: {filepath}")
    except snapshot_service.SnapshotError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command(name="list")
def list_snapshots(
    json_out: _JSON_OPT = False,
    include_baselines: Annotated[
        bool,
        typer.Option("--include-baselines", help="Include auto-saved baselines"),
    ] = False,
    trace: _TRACE_OPT = False,
) -> None:
    """List all available snapshots.

    Examples:
        vibe3 snapshot list
        vibe3 snapshot list --include-baselines
    """
    if trace:
        enable_trace()

    ids = snapshot_service.list_snapshots(include_baselines=include_baselines)

    if json_out:
        typer.echo(json.dumps({"snapshots": ids}, indent=2))
    else:
        typer.echo("=== Available Snapshots ===")
        if not ids:
            typer.echo("  No snapshots found. Use 'vibe3 snapshot save' to create one.")
        else:
            for i, sid in enumerate(ids, 1):
                typer.echo(f"  {i}. {sid}")


@app.command()
def show(
    snapshot_id: Annotated[
        str | None,
        typer.Argument(help="Snapshot ID to show (default: current live structure)"),
    ] = None,
    branch: Annotated[
        str | None,
        typer.Option("--branch", help="Show baseline for specific branch"),
    ] = None,
    json_out: _JSON_OPT = False,
    quiet: Annotated[
        bool, typer.Option("--quiet", help="Suppress next step suggestions")
    ] = False,
    trace: _TRACE_OPT = False,
) -> None:
    """Show snapshot details.

    By default (no arguments), builds and shows the current live structure.
    If snapshot_id is provided, shows a saved snapshot.
    If --branch is provided, shows the saved baseline for that branch.

    Examples:
        vibe3 snapshot show                  # Show current live structure
        vibe3 snapshot show <snapshot-id>   # Show specific saved snapshot
        vibe3 snapshot show --branch main   # Show baseline for 'main' branch
        vibe3 snapshot show --json
    """
    if trace:
        enable_trace()

    try:
        if branch:
            # Load baseline for specific branch
            snapshot = snapshot_service.load_branch_baseline(branch)
            if not snapshot:
                typer.echo(f"No baseline found for branch: {branch}", err=True)
                raise typer.Exit(1)
            title = f"=== Baseline: {snapshot.snapshot_id} (branch: {branch}) ==="
        elif snapshot_id is None:
            # Build current live snapshot (don't save)
            snapshot = snapshot_service.build_snapshot()
            title = "=== Current Live Structure ==="
        else:
            # Load saved snapshot
            snapshot = snapshot_service.load_snapshot(snapshot_id)
            title = f"=== Snapshot: {snapshot.snapshot_id} ==="

        if json_out:
            typer.echo(snapshot.model_dump_json(indent=2))
        else:
            typer.echo(title)
            typer.echo(f"  Branch: {snapshot.branch}")
            typer.echo(f"  Commit: {snapshot.commit}")
            typer.echo(f"  Created: {snapshot.created_at}")
            typer.echo(f"  Root: {snapshot.root}")
            typer.echo("\n  Metrics:")
            typer.echo(f"    Files: {snapshot.metrics.total_files}")
            typer.echo(f"    Total LOC: {snapshot.metrics.total_loc}")
            typer.echo(f"    Functions: {snapshot.metrics.total_functions}")
            typer.echo(f"    Python files: {snapshot.metrics.python_files}")
            typer.echo(f"\n  Modules ({len(snapshot.modules)}):")
            for m in snapshot.modules:
                typer.echo(f"    {m.module}: {m.file_count} files, {m.total_loc} LOC")

            from vibe3.commands.inspect_helpers import suggest_next_step

            suggest_next_step("snapshot_show", quiet)

    except snapshot_service.SnapshotNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def diff(
    baseline: Annotated[
        str | None,
        typer.Argument(help="Baseline snapshot ID (default: current branch baseline)"),
    ] = None,
    json_out: _JSON_OPT = False,
    quiet: Annotated[
        bool, typer.Option("--quiet", help="Suppress next step suggestions")
    ] = False,
    trace: _TRACE_OPT = False,
) -> None:
    """Compare current codebase with a baseline snapshot.

    If no baseline is specified, defaults to the auto-saved baseline for the
    current branch. This gives the net structural change since the last
    flow completion (PR merge or auto-complete).

    Examples:
        vibe3 snapshot diff                  # Compare with current branch baseline
        vibe3 snapshot diff <snapshot-id>    # Compare with specific snapshot
        vibe3 snapshot diff latest           # Compare with latest snapshot
    """
    from vibe3.clients.git_client import GitClient

    if trace:
        enable_trace()

    try:
        # Get baseline snapshot
        if baseline is None:
            # Default: use branch baseline
            git = GitClient()
            current_branch = git.get_current_branch()
            baseline_snapshot = snapshot_service.load_branch_baseline(current_branch)
            if not baseline_snapshot:
                typer.echo(
                    f"No baseline found for current branch '{current_branch}'.\n"
                    "Either:\n"
                    "  - Create a branch baseline: vibe3 snapshot save --as-baseline\n"
                    "  - Specify a baseline snapshot ID: vibe3 snapshot diff <id>\n"
                    "  - Create a baseline by completing the flow "
                    "(PR merge/auto-complete)\n",
                    err=True,
                )
                raise typer.Exit(1)
        elif baseline == "latest":
            # Load latest snapshot
            baseline_snapshot = snapshot_service.load_snapshot(None)
        else:
            # Load specified snapshot
            baseline_snapshot = snapshot_service.load_snapshot(baseline)

        # Build current snapshot
        current_snapshot = snapshot_service.build_snapshot()
        result = compute_diff(baseline_snapshot, current_snapshot)

        if json_out:
            typer.echo(result.model_dump_json(indent=2))
        else:
            typer.echo("=== Structure Diff ===")
            typer.echo(f"  Baseline: {result.baseline_id}")
            typer.echo(f"  Baseline branch: {result.baseline_branch}")
            typer.echo(f"  Current:  {result.current_id}")
            typer.echo(f"  Current branch: {result.current_branch}")
            typer.echo("\n  Summary:")
            typer.echo(
                f"    Files: +{result.summary.files_added} "
                f"-{result.summary.files_removed} "
                f"~{result.summary.files_modified}"
            )
            typer.echo(
                f"    Modules: +{result.summary.modules_added} "
                f"-{result.summary.modules_removed} "
                f"~{result.summary.modules_modified}"
            )
            typer.echo(
                f"    Dependencies: +{result.summary.dependencies_added} "
                f"-{result.summary.dependencies_removed}"
            )
            typer.echo(f"    LOC delta: {result.summary.total_loc_delta:+d}")
            typer.echo(
                f"    Functions delta: {result.summary.total_functions_delta:+d}"
            )

            if result.file_changes:
                typer.echo(f"\n  File Changes ({len(result.file_changes)}):")
                for fc in result.file_changes[:20]:
                    status = {"added": "+", "removed": "-", "modified": "~"}[
                        fc.change_type
                    ]
                    typer.echo(f"    {status} {fc.path}")
                if len(result.file_changes) > 20:
                    typer.echo(f"    ... and {len(result.file_changes) - 20} more")

            if result.warnings:
                typer.echo(f"\n  Warnings ({len(result.warnings)}):")
                for w in result.warnings:
                    typer.echo(f"    [{w.severity}] {w.message}")

            from vibe3.commands.inspect_helpers import suggest_next_step

            suggest_next_step("snapshot_diff", quiet)

    except snapshot_service.SnapshotNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except snapshot_service.SnapshotError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
