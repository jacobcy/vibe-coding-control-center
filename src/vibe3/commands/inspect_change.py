"""Inspect change commands - PR/Commit 改动分析."""

from typing import Annotated

import typer

from vibe3.commands.inspect_helpers import build_change_analysis, validate_pr_number
from vibe3.utils.trace import enable_trace


def register(app: typer.Typer) -> None:
    """Register change analysis commands on the given app."""

    @app.command()
    def pr(
        pr_number: Annotated[int, typer.Argument(help="PR number")],
        json_out: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
        ] = False,
        trace: Annotated[
            bool, typer.Option("--trace", help="Enable call tracing + DEBUG logs")
        ] = False,
    ) -> None:
        """PR change analysis with DAG impact.

        Shows:
        - Changed symbols (functions in diff hunks)
        - Impacted modules (DAG upstream dependencies)
        - Risk score and block status

        Example: vibe inspect pr 42
        """
        import json

        if trace:
            enable_trace()

        # Validate PR number
        validate_pr_number(pr_number)

        result = build_change_analysis("pr", str(pr_number))

        if json_out:
            typer.echo(json.dumps(result, indent=2, default=str))
            return

        _print_change_analysis("pr", str(pr_number), result)

    @app.command()
    def commit(
        sha: Annotated[str, typer.Argument(help="Commit SHA")],
        json_out: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
        ] = False,
        trace: Annotated[
            bool, typer.Option("--trace", help="Enable call tracing + DEBUG logs")
        ] = False,
    ) -> None:
        """Commit change analysis with DAG impact.

        Shows:
        - Changed symbols (functions in diff hunks)
        - Impacted modules (DAG upstream dependencies)
        - Risk score

        Example: vibe inspect commit HEAD~1
        """
        import json

        if trace:
            enable_trace()

        result = build_change_analysis("commit", sha)

        if json_out:
            typer.echo(json.dumps(result, indent=2, default=str))
            return

        score = result["score"]
        assert isinstance(score, dict)
        dag = result["dag"]
        assert isinstance(dag, dict)
        changed_symbols = result.get("changed_symbols", {})
        assert isinstance(changed_symbols, dict)

        typer.echo(f"=== Commit {sha} Analysis ===")

        # Show changed symbols
        if changed_symbols:
            typer.echo("\n  Changed symbols:")
            for file, symbols in changed_symbols.items():
                typer.echo(f"    {file}:")
                for sym in symbols:
                    typer.echo(f"      - {sym}")

        # Show impacted modules
        impacted = dag.get("impacted_modules", [])
        assert isinstance(impacted, list)
        typer.echo(f"\n  Impacted modules: {len(impacted)}")
        if impacted:
            for module in impacted[:10]:  # Show first 10
                typer.echo(f"    - {module}")
            if len(impacted) > 10:
                typer.echo(f"    ... and {len(impacted) - 10} more")

        # Show risk score
        typer.echo(f"\n  Risk score: {score['score']} ({score['level']})")


def _print_change_analysis(source_type: str, identifier: str, result: dict) -> None:
    """Print change analysis result in consistent format.

    Args:
        source_type: "pr" | "commit" | "branch"
        identifier: PR number, commit SHA, or branch name
        result: Analysis result from build_change_analysis()
    """
    import typer

    score = result["score"]
    assert isinstance(score, dict)
    dag = result["dag"]
    assert isinstance(dag, dict)
    changed_symbols = result.get("changed_symbols", {})
    assert isinstance(changed_symbols, dict)

    # Title based on source type
    if source_type == "pr":
        typer.echo(f"=== PR #{identifier} Analysis ===")
    elif source_type == "commit":
        typer.echo(f"=== Commit {identifier} Analysis ===")
    else:
        typer.echo(f"=== Branch {identifier} Analysis ===")

    # Show skipped files if any
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

    # Show changed symbols
    if changed_symbols:
        typer.echo("\n  Changed symbols:")
        for file, symbols in changed_symbols.items():
            typer.echo(f"    {file}:")
            for sym in symbols:
                typer.echo(f"      - {sym}")

    # Show impacted modules
    impacted = dag.get("impacted_modules", [])
    assert isinstance(impacted, list)
    typer.echo(f"\n  Impacted modules: {len(impacted)}")
    if impacted:
        for module in impacted[:10]:  # Show first 10
            typer.echo(f"    - {module}")
        if len(impacted) > 10:
            typer.echo(f"    ... and {len(impacted) - 10} more")

    # Show risk score
    typer.echo(f"\n  Risk score: {score['score']} ({score['level']})")

    # Show block status for PR
    if source_type == "pr":
        typer.echo(f"  Block: {score['block']}")

    # Show skipped files note (if any were skipped)
    if skipped_files:
        typer.echo(
            f"\n  ℹ️  Note: {len(skipped_files)} file(s) were skipped"
            " as they no longer exist in the repository."
        )
