"""Inspect symbols command - 符号引用分析."""

import json
import sys
from io import StringIO
from typing import Annotated

import typer
from loguru import logger

from vibe3.analysis.serena_service import SerenaService
from vibe3.utils.trace import enable_trace


def register(app: typer.Typer) -> None:
    """Register the symbols command on the given app."""

    @app.command()
    def symbols(
        symbol_spec: Annotated[
            str,
            typer.Argument(help="Symbol specification: <file>:<symbol> or <file>"),
        ] = "",
        json_out: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
        ] = False,
        quiet: Annotated[
            bool, typer.Option("--quiet", help="Suppress next step suggestions")
        ] = False,
        trace: Annotated[
            bool, typer.Option("--trace", help="Enable call tracing + DEBUG logs")
        ] = False,
    ) -> None:
        """Show symbol references with detailed locations.

        Two query modes (file context required):

        1. <file>:<symbol>  - Find specific symbol in file
           vibe inspect symbols src/vibe3/services/dag_service.py:build_module_graph

        2. <file>           - List all symbols in file
           vibe inspect symbols src/vibe3/services/dag_service.py

        Reference counts show:
        - Regular functions: Number of times called in code
        - CLI commands: Marked as "CLI command" (invoked via CLI, not code)

        Output includes:
        - Total reference count
        - Each reference location (file:line)
        - Context snippet showing the usage

        Examples:
            vibe inspect symbols src/vibe3/services/dag_service.py:_file_to_module
            vibe inspect symbols src/vibe3/commands/inspect.py --json
        """
        if trace:
            enable_trace()

        # Suppress Serena warnings by redirecting stderr temporarily
        old_stderr = sys.stderr
        sys.stderr = StringIO()

        try:
            if not symbol_spec:
                sys.stderr = old_stderr
                typer.echo("Error: Please provide a symbol specification.", err=True)
                typer.echo("\nUsage:")
                typer.echo("  vibe inspect symbols <file>:<symbol>")
                typer.echo("  vibe inspect symbols <file>")
                raise typer.Exit(code=1)

            svc = SerenaService()

            if ":" in symbol_spec:
                parts = symbol_spec.split(":", 1)
                file_path, symbol_name = parts[0], parts[1]
                result = svc.analyze_symbol(symbol_name, file_path)
            elif symbol_spec.endswith(".py"):
                result = svc.analyze_file(symbol_spec)
            else:
                sys.stderr = old_stderr
                typer.echo(
                    "Error: Symbol-only search requires file context.",
                    err=True,
                )
                typer.echo(f"Use: vibe inspect symbols <file>:{symbol_spec}")
                raise typer.Exit(code=1)

            sys.stderr = old_stderr

            if json_out:
                typer.echo(json.dumps(result, indent=2))
                return

            if "symbols" in result:
                _print_symbols_table(result)
            else:
                _print_symbol_references(result)

            from vibe3.commands.inspect_helpers import suggest_next_step

            suggest_next_step("inspect_symbols", quiet)

        except Exception as e:
            sys.stderr = old_stderr
            logger.debug(f"Skipping: {e}")
            raise


def _print_symbol_references(result: dict) -> None:
    """Print single symbol references in simple format."""
    symbol = result["symbol"]
    defined_in = result["defined_in"]
    ref_count = result["reference_count"]
    symbol_type = result.get("type", "function")

    typer.echo(f"=== Symbol: {symbol} ===")
    typer.echo(f"  Defined in: {defined_in}")

    if symbol_type == "cli_command":
        typer.echo("  Type: CLI command (invoked via CLI, not in code)")
    else:
        typer.echo(f"  References: {ref_count}")

    if result["references"]:
        typer.echo("\n  Referenced by:")
        for ref in result["references"]:
            typer.echo(f"    {ref['file']}:{ref['line']}")
            if ref.get("context"):
                ctx_lines = ref["context"].split("\n")
                for line in ctx_lines[:2]:
                    typer.echo(f"      {line.strip()}")


def _print_symbols_table(result: dict) -> None:
    """Print file symbols in simple format (like inspect structure)."""
    typer.echo(f"=== Symbols: {result['file']} ===")
    symbols = result.get("symbols", [])
    typer.echo(f"  Total symbols: {len(symbols)}")

    for sym in symbols:
        name = sym["name"]
        refs = sym.get("references", 0)
        symbol_type = sym.get("type", "function")

        if symbol_type == "cli_command":
            typer.echo(f"    {name}  (CLI command, 0 code refs)")
        else:
            typer.echo(f"    {name}  ({refs} refs)")
