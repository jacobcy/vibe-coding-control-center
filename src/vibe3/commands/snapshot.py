"""Snapshot command - 代码库结构快照管理."""

import json
from typing import Annotated

import typer

from vibe3.analysis import snapshot_service
from vibe3.analysis.snapshot_diff import compute_diff
from vibe3.utils.trace import enable_trace

app = typer.Typer(
    name="snapshot",
    help="Manage structure snapshots for code quality tracking",
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
    """Build a structure snapshot from current codebase.

    The snapshot captures:
    - File structure (LOC, functions, dependencies)
    - Module aggregation
    - Dependency graph
    - Quality metrics

    This is the canonical structure entrypoint; use `snapshot show` for review.

    Examples:
        vibe3 snapshot build
        vibe3 snapshot build --json
    """
    if trace:
        enable_trace()

    try:
        snapshot = snapshot_service.build_snapshot()
        filepath = snapshot_service.save_snapshot(snapshot)

        if json_out:
            typer.echo(snapshot.model_dump_json(indent=2))
        else:
            typer.echo(f"✓ Snapshot built: {snapshot.snapshot_id}")
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
    trace: _TRACE_OPT = False,
) -> None:
    """List all available snapshots.

    Examples:
        vibe3 snapshot list
    """
    if trace:
        enable_trace()

    ids = snapshot_service.list_snapshots()

    if json_out:
        typer.echo(json.dumps({"snapshots": ids}, indent=2))
    else:
        typer.echo("=== Available Snapshots ===")
        if not ids:
            typer.echo(
                "  No snapshots found. Use 'vibe3 snapshot build' to create one."
            )
        else:
            for i, sid in enumerate(ids, 1):
                typer.echo(f"  {i}. {sid}")


@app.command()
def show(
    snapshot_id: Annotated[
        str | None,
        typer.Argument(help="Snapshot ID to show (default: latest)"),
    ] = None,
    json_out: _JSON_OPT = False,
    trace: _TRACE_OPT = False,
) -> None:
    """Show snapshot details.

    Examples:
        vibe3 snapshot show                  # Show latest snapshot
        vibe3 snapshot show <snapshot-id>   # Show specific snapshot
        vibe3 snapshot show --json
    """
    if trace:
        enable_trace()

    try:
        snapshot = snapshot_service.load_snapshot(snapshot_id)

        if json_out:
            typer.echo(snapshot.model_dump_json(indent=2))
        else:
            typer.echo(f"=== Snapshot: {snapshot.snapshot_id} ===")
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
            for m in snapshot.modules[:10]:
                typer.echo(f"    {m.module}: {m.file_count} files, {m.total_loc} LOC")
            if len(snapshot.modules) > 10:
                typer.echo(f"    ... and {len(snapshot.modules) - 10} more")

    except snapshot_service.SnapshotNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def diff(
    baseline: Annotated[
        str,
        typer.Argument(help="Baseline snapshot ID (use 'latest' for most recent)"),
    ],
    json_out: _JSON_OPT = False,
    trace: _TRACE_OPT = False,
) -> None:
    """Compare current codebase with a baseline snapshot.

    Examples:
        vibe3 snapshot diff <snapshot-id>    # Compare with specific snapshot
        vibe3 snapshot diff latest           # Compare with latest snapshot
    """
    if trace:
        enable_trace()

    try:
        baseline_snapshot = snapshot_service.load_snapshot(
            None if baseline == "latest" else baseline
        )
        current_snapshot = snapshot_service.build_snapshot()
        result = compute_diff(baseline_snapshot, current_snapshot)

        if json_out:
            typer.echo(result.model_dump_json(indent=2))
        else:
            typer.echo("=== Structure Diff ===")
            typer.echo(f"  Baseline: {result.baseline_id}")
            typer.echo(f"  Current:  {result.current_id}")
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

    except snapshot_service.SnapshotNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except snapshot_service.SnapshotError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
