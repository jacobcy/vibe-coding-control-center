"""Validated positive symbol evidence for ``vibe3 inspect symbols``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
import yaml

from vibe3.analysis.symbol_reference_service import (
    SerenaSymbolReferenceProvider,
    SymbolInspectionResult,
    inspect_symbol,
)
from vibe3.commands.common import enable_method_trace


def register(app: typer.Typer) -> None:
    """Register the evidence-only symbols command."""

    @app.command()
    def symbols(
        symbol_spec: Annotated[
            str,
            typer.Argument(help="Explicit symbol query: <file>:<symbol>"),
        ],
        json_out: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
        ] = False,
        yaml_out: Annotated[
            bool, typer.Option("--yaml", help="Output as YAML")
        ] = False,
        quiet: Annotated[
            bool, typer.Option("--quiet", help="Suppress next step suggestions")
        ] = False,
        trace: Annotated[
            bool,
            typer.Option("--trace", help="Enable call tracing (set VIBE3_TRACE=1)"),
        ] = False,
    ) -> None:
        """Show validated definition and observed static references."""
        from vibe3.clients import GitClient, SerenaClient

        del quiet
        if trace:
            enable_method_trace()
        if ":" not in symbol_spec:
            typer.echo("Error: expected <file>:<symbol>", err=True)
            raise typer.Exit(1)
        file_name, symbol = symbol_spec.rsplit(":", 1)
        if not file_name or not symbol:
            typer.echo("Error: expected <file>:<symbol>", err=True)
            raise typer.Exit(1)

        repo_root = Path(GitClient().get_worktree_root())
        path = Path(file_name)
        if not path.is_absolute():
            path = repo_root / path
        provider = SerenaSymbolReferenceProvider(
            SerenaClient(project_root=str(repo_root))
        )
        result = inspect_symbol(
            path,
            symbol,
            provider=provider,
            repo_root=repo_root,
        )
        _render(result, json_out=json_out, yaml_out=yaml_out)
        if result.status in {"disabled", "error", "not_found"}:
            raise typer.Exit(1)


def _render(
    result: SymbolInspectionResult,
    *,
    json_out: bool,
    yaml_out: bool,
) -> None:
    if json_out:
        typer.echo(result.model_dump_json(indent=2))
        return
    payload = json.loads(result.model_dump_json())
    if yaml_out:
        typer.echo(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True))
        return

    query = result.query
    typer.echo(f"Status: {result.status}")
    if query is not None:
        typer.echo(f"Query: {query.file}:{query.symbol}")
    typer.echo(f"Provider: {result.provenance.provider} {result.provenance.version}")
    if result.definition is not None:
        source_range = result.definition.range
        typer.echo(
            f"Definition: {result.definition.path}:"
            f"{source_range.start_line}-{source_range.end_line}"
        )
    if result.observation is not None:
        typer.echo(
            "Observed static references: "
            f"{result.observation.observed_reference_count} (not complete)"
        )
    for reference in result.references:
        typer.echo(f"Reference: {reference.path}:{reference.range.start_line}")
    for unknown in result.unknowns:
        typer.echo(f"Unknown: {unknown.code}: {unknown.message}")
