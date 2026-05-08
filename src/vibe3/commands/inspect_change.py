"""Inspect change commands."""

import json
from typing import Annotated

import typer
import yaml

from vibe3.analysis.inspect_query_service import build_change_analysis
from vibe3.utils.trace import enable_trace


def register(app: typer.Typer) -> None:
    """Register change analysis commands."""

    @app.command(name="uncommit")
    def uncommit(
        json_out: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
        ] = False,
        yaml_out: Annotated[
            bool, typer.Option("--yaml", help="Output as YAML")
        ] = False,
        trace: Annotated[
            bool, typer.Option("--trace", help="Enable call tracing + DEBUG logs")
        ] = False,
    ) -> None:
        """Run analysis for uncommitted working tree changes."""

        if trace:
            enable_trace()

        result = build_change_analysis("uncommit", "working-tree")

        if json_out:
            typer.echo(json.dumps(result, indent=2, default=str))
            return
        elif yaml_out:
            # Convert to JSON-serializable dict first (handles enums, etc.)
            clean_result = json.loads(json.dumps(result, default=str))
            typer.echo(
                yaml.dump(clean_result, default_flow_style=False, allow_unicode=True)
            )
            return

        _print_change_analysis("uncommitted", "working-tree", result)


def _print_change_analysis(source_type: str, identifier: str, result: dict) -> None:
    """Print change analysis result."""
    import typer

    score = result["score"]
    assert isinstance(score, dict)
    dag = result["dag"]
    assert isinstance(dag, dict)
    changed_symbols = result.get("changed_symbols", {})
    assert isinstance(changed_symbols, dict)

    typer.echo(f"=== Branch {identifier} Analysis ===")

    impact = result.get("impact", {})
    skipped_files = []
    if isinstance(impact, dict):
        skipped_files = impact.get("skipped_files", [])
        if skipped_files:
            typer.echo(
                f"\n  ⚠️  Skipped {len(skipped_files)} files (no longer in repository):"
            )
            for file in skipped_files[:5]:  # Show first 5
                typer.echo(f"    - {file}")
            if len(skipped_files) > 5:
                typer.echo(f"    ... and {len(skipped_files) - 5} more")

    if changed_symbols:
        typer.echo("\n  Changed symbols:")
        for file, symbols in changed_symbols.items():
            typer.echo(f"    {file}:")
            for sym in symbols:
                typer.echo(f"      - {sym}")

    impacted = dag.get("impacted_modules", [])
    assert isinstance(impacted, list)
    typer.echo(f"\n  Impacted modules: {len(impacted)}")
    if impacted:
        for module in impacted[:10]:  # Show first 10
            typer.echo(f"    - {module}")
        if len(impacted) > 10:
            typer.echo(f"    ... and {len(impacted) - 10} more")

    typer.echo(f"\n  Risk score: {score['score']} ({score['level']})")

    if skipped_files:
        typer.echo(
            f"\n  ℹ️  Note: {len(skipped_files)} file(s) were skipped"
            " as they no longer exist in the repository."
        )
