"""Inspect command - 信息提供层，输出结构化数据供 vibe review 消费."""

import json
from typing import Annotated, Any, cast

import typer

from vibe3.analysis import command_analyzer, dag_service, structure_service
from vibe3.analysis.command_analyzer_helpers import find_command_file
from vibe3.commands.inspect_base import register as register_base
from vibe3.commands.inspect_change import register as register_change
from vibe3.commands.inspect_symbols import register as register_symbols
from vibe3.utils.trace import enable_trace

app = typer.Typer(
    name="inspect",
    help="Provide code analysis information",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

_JSON_OPT = Annotated[bool, typer.Option("--json", help="Output as JSON")]
_TRACE_OPT = Annotated[
    bool, typer.Option("--trace", help="Enable call tracing + DEBUG logs")
]


def _list_analyzable_top_level_commands(
    commands_root: str = "src/vibe3/commands",
) -> list[str]:
    """Return root CLI commands that have analyzable command files."""
    from vibe3.cli import app as root_app  # noqa: I001
    from typer.main import get_command  # noqa: I001

    names: list[str] = []
    click_app = cast(Any, get_command(root_app))
    for name in click_app.commands.keys():
        if name and find_command_file(name, None, commands_root):
            names.append(name)
    return sorted(dict.fromkeys(names))


# Register extracted commands
register_symbols(app)
register_base(app)
register_change(app)


@app.command(name="files")
def files_(
    file: Annotated[str, typer.Argument(help="File to analyze")] = "",
    json_out: _JSON_OPT = False,
    trace: _TRACE_OPT = False,
) -> None:
    """Analyze file structure (functions, LOC, dependencies).

    Examples:
        vibe3 inspect files src/vibe3/services/flow_service.py
        vibe3 inspect files                    # Analyze all Python files
    """
    if trace:
        enable_trace()

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
        else:
            typer.echo("=== Python Files Summary ===")
            for r in results:
                typer.echo(
                    f"  {r['path']}: {r['total_loc']} LOC, "
                    f"{r['function_count']} functions"
                )


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
        enable_trace()

    if not command:
        names = ", ".join(_list_analyzable_top_level_commands())
        typer.echo(f"Available commands: {names}")
        return

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
