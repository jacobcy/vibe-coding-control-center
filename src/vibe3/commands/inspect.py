"""Inspect command - 信息提供层，输出结构化数据供 vibe review 消费."""

import json
from pathlib import Path
from typing import Annotated

import typer
import yaml

from vibe3.analysis import (
    SerenaService,
    command_analyzer,
    dag_service,
    structure_service,
)
from vibe3.commands.common import enable_method_trace
from vibe3.commands.inspect_base import register as register_base
from vibe3.commands.inspect_change import register as register_change
from vibe3.commands.inspect_symbols import register as register_symbols
from vibe3.exceptions import SerenaError
from vibe3.models import CallNode, CommandInspection

app = typer.Typer(
    name="inspect",
    help="""Single-file & change analysis (real-time).

When to use inspect:
  - Analyzing one file structure (LOC, functions, imports)
  - Looking up where a symbol is used
  - Finding dead code
  - Analyzing impact of a single change (branch / uncommitted)

Subcommands:
  files [<file>]             Structure of one file (default: all Python files)
  symbols <file>:<symbol>    Find symbol references
  base [<branch>]            Key impact vs base branch
  uncommit                   Impact analysis of uncommitted changes
  dead-code [<root>]         Find unused functions
  commands [<cmd> <subcmd>]  Static analysis of CLI command structure

For project-level structure snapshots → use:
  vibe3 snapshot             (persistent structure tracking)

Examples:
  vibe3 inspect files src/vibe3/services/
  vibe3 inspect symbols src/vibe3/cli.py:app
  vibe3 inspect base main""",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

_JSON_OPT = Annotated[bool, typer.Option("--json", help="Output as JSON")]
_TRACE_OPT = Annotated[
    bool, typer.Option("--trace", help="Enable call tracing (set VIBE3_TRACE=1)")
]


def _list_analyzable_top_level_commands(
    commands_root: str | None = None,
) -> list[str]:
    """Return root CLI commands that have analyzable command files.

    Uses filesystem-based heuristic to discover top-level commands by scanning
    the commands/ directory. This approach avoids layer violation (importing from
    cli layer) but has limitations:

    - Assumes top-level commands have simple filenames (no underscores)
    - Relies on hardcoded exclusion list (_non_command)
    - Does NOT validate commands are actually registered in Typer app

    Future improvement: Consider adding validation against registered Typer commands
    without creating layer violation.
    """
    if commands_root is None:
        from vibe3.config import get_commands_root

        commands_root = get_commands_root()
    root = Path(commands_root)
    if not root.is_dir():
        return []

    # Files in commands/ that are not top-level CLI commands
    _non_command = {
        "__init__.py",
        "common.py",
        "command_options.py",
        "output_format.py",
    }

    names: list[str] = []
    for entry in sorted(root.iterdir()):
        if not entry.name.endswith(".py"):
            continue
        if entry.name in _non_command:
            continue
        stem = entry.stem
        # Top-level command files have simple names (no underscores);
        # helper modules like inspect_helpers.py, flow_status.py are excluded.
        if "_" in stem:
            continue
        # Note: This is a filesystem heuristic. We assume files with simple names
        # in commands/ are top-level commands. The tautological check
        # (find_command_file) has been removed since we already know the file exists
        # (we're iterating over it).
        names.append(stem)
    return sorted(dict.fromkeys(names))


# Register extracted commands
register_symbols(app)
register_base(app)
register_change(app)


@app.command(name="files")
def files_(
    file: Annotated[str, typer.Argument(help="File to analyze")] = "",
    json_out: _JSON_OPT = False,
    yaml_out: Annotated[bool, typer.Option("--yaml", help="Output as YAML")] = False,
    quiet: Annotated[
        bool, typer.Option("--quiet", help="Suppress next step suggestions")
    ] = False,
    trace: _TRACE_OPT = False,
) -> None:
    """Analyze file structure (functions, LOC, dependencies).

    Examples:
        vibe3 inspect files src/vibe3/services/flow_service.py
        vibe3 inspect files                    # Analyze all Python files
    """
    if trace:
        enable_method_trace()

    if file:
        result = structure_service.analyze_file(file)

        if file.endswith(".py"):
            result.imports = dag_service._extract_imports(file)

            module_graph = dag_service.build_module_graph()
            current_module = dag_service._file_to_module(file)

            imported_by: list[str] = []
            for module, node in module_graph.items():
                if current_module in node.imports:
                    imported_by.append(module)
            result.imported_by = sorted(imported_by)

        if json_out:
            typer.echo(json.dumps(result.model_dump(), indent=2))
        elif yaml_out:
            typer.echo(
                yaml.dump(
                    result.model_dump(), default_flow_style=False, allow_unicode=True
                )
            )
        else:
            typer.echo(f"=== File: {file} ===")
            typer.echo(f"  Language  : {result.language}")
            typer.echo(f"  Total LOC : {result.total_loc}")
            typer.echo(f"  Functions : {result.function_count}")
            for fn in result.functions:
                typer.echo(f"    L{fn.line:4d}  {fn.name}  ({fn.loc} lines)")

            if result.imports:
                typer.echo(f"\n  Imports ({len(result.imports)}):")
                for imp in result.imports:
                    typer.echo(f"    - {imp}")

            if result.imported_by:
                typer.echo(f"\n  Imported by ({len(result.imported_by)}):")
                for imp_by in result.imported_by:
                    typer.echo(f"    - {imp_by}")
    else:
        results = [
            file_struct.model_dump()
            for file_struct in structure_service.collect_python_file_structures()
        ]

        if json_out:
            typer.echo(json.dumps(results, indent=2))
        elif yaml_out:
            typer.echo(yaml.dump(results, default_flow_style=False, allow_unicode=True))
        else:
            typer.echo("=== Python Files Summary ===")
            for r in results:
                typer.echo(
                    f"  {r['path']}: {r['total_loc']} LOC, "
                    f"{r['function_count']} functions"
                )

        if file and not json_out:
            from vibe3.commands.inspect_helpers import suggest_next_step

            suggest_next_step("inspect_files", quiet)


@app.command()
def commands(
    command: Annotated[str, typer.Argument(help="Command name")] = "",
    subcommand: Annotated[str, typer.Argument(help="Subcommand name")] = "",
    json_out: _JSON_OPT = False,
    yaml_out: Annotated[bool, typer.Option("--yaml", help="Output as YAML")] = False,
    tree_out: Annotated[
        bool, typer.Option("--tree", help="Output as ASCII tree")
    ] = False,
    mermaid_out: Annotated[
        bool, typer.Option("--mermaid", help="Output as Mermaid diagram")
    ] = False,
    trace: _TRACE_OPT = False,
) -> None:
    """Show vibe command structure (static analysis, no execution).

    Examples:
        vibe inspect commands
        vibe inspect commands pr
        vibe inspect commands pr show --yaml
        vibe inspect commands pr show --tree
        vibe inspect commands pr show --mermaid
    """
    if trace:
        enable_method_trace()

    if not command:
        names = _list_analyzable_top_level_commands()
        if any([json_out, yaml_out, tree_out, mermaid_out]):
            call_tree = [CallNode(name=name, line=0) for name in names]
            result = CommandInspection(
                command="vibe",
                file="src/vibe3/cli.py",
                call_depth=1,
                call_tree=call_tree,
            )
            # Proceed to formatting logic below
        else:
            typer.echo("=== vibe3 command structure ===")
            typer.echo(f"Top-level commands: {', '.join(names)}")
            typer.echo()
            typer.echo("Use this command to inspect a specific call tree:")
            typer.echo("  vibe3 inspect commands pr show          # YAML format")
            typer.echo("  vibe3 inspect commands pr show --tree   # ASCII tree")
            typer.echo("  vibe3 inspect commands pr show --mermaid # Mermaid diagram")
            typer.echo()
            typer.echo("Examples:")
            typer.echo("  vibe3 inspect commands review")
            return
    else:
        result = command_analyzer.analyze_command(command, subcommand or None)

    # Output in requested format
    if json_out:
        typer.echo(result.to_json())
    elif yaml_out:
        typer.echo(result.to_yaml())
    elif tree_out:
        typer.echo(result.to_tree())
    elif mermaid_out:
        typer.echo(result.to_mermaid())
    else:
        # Default: YAML format
        typer.echo(result.to_yaml())


@app.command(name="dead-code")
def dead_code(
    root: Annotated[
        str, typer.Argument(help="Root directory to scan (default: from config)")
    ] = "",
    json_out: _JSON_OPT = False,
    yaml_out: Annotated[bool, typer.Option("--yaml", help="Output as YAML")] = False,
    min_confidence: Annotated[
        str,
        typer.Option(
            "--min-confidence",
            help="Minimum confidence level to show (high/medium/low)",
        ),
    ] = "low",
    quiet: Annotated[
        bool, typer.Option("--quiet", help="Suppress next step suggestions")
    ] = False,
    trace: _TRACE_OPT = False,
) -> None:
    """Scan for dead code (unused functions).

    Identifies functions and methods with zero references.

    Confidence levels:
    - high: Regular functions with 0 refs
    - medium: Private functions with 0 refs (might be used dynamically)
    - low: All findings (including medium confidence)

    Excludes:
    - CLI commands (invoked via CLI, not code)
    - Test functions (test_*, pytest fixtures)
    - Special methods (__init__, __str__, etc.)

    Examples:
        vibe3 inspect dead-code
        vibe3 inspect dead-code src/vibe3 --min-confidence=high
        vibe3 inspect dead-code --json
        vibe3 inspect dead-code --yaml
    """
    if trace:
        enable_method_trace()

    # Validate min_confidence
    valid_confidences = ["high", "medium", "low"]
    if min_confidence not in valid_confidences:
        typer.echo(
            f"Error: --min-confidence must be one of {valid_confidences}",
            err=True,
        )
        raise typer.Exit(1)

    if not root:
        from vibe3.config import get_source_root

        root = get_source_root()

    try:
        service = SerenaService()
        report = service.scan_dead_code(root)

        # Filter by confidence
        if min_confidence == "high":
            report.findings = [f for f in report.findings if f.confidence == "high"]
            report.dead_code_count = len(report.findings)
        elif min_confidence == "medium":
            report.findings = [
                f for f in report.findings if f.confidence in ["high", "medium"]
            ]
            report.dead_code_count = len(report.findings)

        if json_out:
            typer.echo(report.model_dump_json(indent=2))
        elif yaml_out:
            typer.echo(
                yaml.dump(
                    report.model_dump(), default_flow_style=False, allow_unicode=True
                )
            )
        else:
            typer.echo("=== Dead Code Report ===")
            typer.echo(f"  Total symbols scanned: {report.total_symbols}")
            typer.echo(f"  Dead code found: {report.dead_code_count}")
            typer.echo(f"  Excluded: {report.excluded_count}")
            typer.echo(f"  Root: {root}")
            typer.echo(f"  Min confidence: {min_confidence}")

            if report.findings:
                typer.echo(f"\n  Findings ({len(report.findings)}):")
                for finding in report.findings:
                    typer.echo(
                        f"    [{finding.confidence.upper():6}] "
                        f"{finding.file}:{finding.symbol}"
                    )
                    typer.echo(f"             {finding.reason}")
            else:
                typer.echo("\n  ✓ No dead code found!")

            if report.excluded and min_confidence == "low":
                typer.echo(f"\n  Excluded ({len(report.excluded)}):")
                for exc in report.excluded[:10]:  # Show first 10
                    typer.echo(f"    {exc}")
                if len(report.excluded) > 10:
                    typer.echo(f"    ... and {len(report.excluded) - 10} more")

            from vibe3.commands.inspect_helpers import suggest_next_step

            suggest_next_step("inspect_dead_code", quiet)

    except SerenaError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Unexpected error: {e}", err=True)
        raise typer.Exit(2)
