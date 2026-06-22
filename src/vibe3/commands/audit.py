#!/usr/bin/env python3
"""Audit command handlers for observation collection."""

from __future__ import annotations

from typing import Annotated

import typer

from vibe3.models.flow import FlowState

app = typer.Typer(
    help="""Audit and observation commands.

Collects structured observations from flow states for audit trail and analysis.

Examples:
  vibe3 audit observe                    # Collect observations from candidate flows
  vibe3 audit observe --dry-run          # Preview observations without persisting
  vibe3 audit observe --flow-count 2     # Limit to 2 flows
  vibe3 audit observe --branch task/issue-123  # Observe specific branch

For more details: vibe3 audit observe --help
""",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


@app.command("observe")
def observe(
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Preview observations without persisting to shared directory",
        ),
    ] = False,
    flow_count: Annotated[
        int,
        typer.Option(
            "--flow-count",
            "-n",
            help="Maximum number of flows to observe (default: 3)",
        ),
    ] = 3,
    branch: Annotated[
        str | None,
        typer.Option(
            "--branch",
            "-b",
            help="Observe a specific branch instead of auto-selecting candidates",
        ),
    ] = None,
    all_flows: Annotated[
        bool,
        typer.Option(
            "--all",
            help="Include all flows, not just candidates (for analysis)",
        ),
    ] = False,
) -> None:
    """Collect observations from flow states.

    Observations are structured records of flow anomalies, failures, and patterns.
    They are persisted to .git/shared/observations/ for cross-worktree visibility.

    Examples:
      # Collect observations from up to 3 candidate flows
      vibe3 audit observe

      # Preview what would be observed without writing files
      vibe3 audit observe --dry-run

      # Observe specific branch
      vibe3 audit observe --branch task/issue-2956

      # Analyze all flows (not just candidates)
      vibe3 audit observe --all --dry-run
    """
    from vibe3.services.observation_collector import ObservationCollector

    typer.echo("=== Audit Observation Collection ===\n")

    # Load flows
    flows = _load_flows()

    if not flows:
        typer.echo("No flows found.")
        raise typer.Exit(0)

    typer.echo(f"Loaded {len(flows)} total flows\n")

    # Filter to specific branch if requested
    if branch:
        flows = [f for f in flows if f.branch == branch]
        if not flows:
            typer.echo(f"No flow found for branch: {branch}")
            raise typer.Exit(1)
        typer.echo(f"Observing specific branch: {branch}\n")

    # Initialize collector
    collector = ObservationCollector()

    # Select candidates (unless --all flag)
    if not all_flows:
        candidates = collector.select_candidates(flows, limit=flow_count)
        typer.echo(f"Selected {len(candidates)} candidate flows:")
        for i, f in enumerate(candidates, 1):
            status_info: str = f.flow_status
            if f.blocked_reason:
                status_info += f" ({f.blocked_reason[:50]}...)"
            typer.echo(f"  {i}. {f.branch} [{status_info}]")
        typer.echo()

        if not candidates:
            typer.echo("No candidate flows to observe.")
            raise typer.Exit(0)

        flows_to_observe = candidates
    else:
        flows_to_observe = flows[:flow_count]

    # Collect observations
    typer.echo("Collecting observations...")
    observations = collector.collect(flows_to_observe, dry_run=dry_run)

    if not observations:
        typer.echo("\nNo new observations generated.")
        raise typer.Exit(0)

    # Display results
    typer.echo(f"\n=== Observations ({len(observations)}) ===\n")

    for i, obs in enumerate(observations, 1):
        typer.echo(f"--- Observation {i} ---")
        typer.echo(f"ID: {obs.observation_id}")
        typer.echo(f"Type: {obs.observation_type}")
        typer.echo(f"Branch: {obs.source_window.branch}")
        typer.echo(f"Symptom: {obs.symptom}")
        typer.echo(f"Layer: {obs.affected_layer.value}")
        typer.echo(f"Confidence: {obs.confidence}")
        typer.echo(f"Watermark: {obs.source_watermark}")
        typer.echo()

    if dry_run:
        typer.echo(
            "[DRY-RUN] Observations would be persisted to " ".git/shared/observations/"
        )
    else:
        typer.echo(f"Observations persisted to {collector.shared_dir}")

    typer.echo(f"\nSummary: {len(observations)} observations collected")


def _load_flows() -> list[FlowState]:
    """Load all flows from flow status command.

    Returns:
        List of FlowState objects
    """
    import json
    import subprocess

    try:
        # Run flow status command to get all flows
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "src/vibe3/cli.py",
                "flow",
                "status",
                "--all",
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        # Parse JSON output (it's a list directly, not wrapped in {"flows": ...})
        data = json.loads(result.stdout)

        # Convert to FlowState objects
        flows = []
        for item in data:  # data is already a list
            flow = FlowState(**item)
            flows.append(flow)

        return flows

    except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError) as e:
        # Fallback: return empty list
        print(f"Warning: Failed to load flows: {e}")
        return []


if __name__ == "__main__":
    app()
