"""Inspect command - 信息提供层，输出结构化数据供 vibe review 消费."""

import json
from typing import Annotated

import typer

from vibe3.commands.inspect_base import register as register_base
from vibe3.commands.inspect_change import register as register_change
from vibe3.commands.inspect_symbols import register as register_symbols
from vibe3.services import (
    command_analyzer,
    dag_service,
    metrics_service,
    structure_service,
)
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

# Register extracted commands
register_symbols(app)
register_base(app)
register_change(app)


@app.command()
def metrics(
    json_out: _JSON_OPT = False,
    trace: _TRACE_OPT = False,
) -> None:
    """Show code metrics (LOC, file counts, limit violations)."""
    if trace:
        enable_trace()

    report = metrics_service.collect_metrics()

    if json_out:
        typer.echo(json.dumps(report.model_dump(), indent=2))
        return

    shell = report.shell
    python = report.python

    # Shell Metrics
    typer.echo("=== Shell Metrics ===")
    typer.echo(
        f"  Total LOC : {shell.total_loc} / {shell.limit_total} "
        f"{'✅' if shell.total_ok else '❌'}"
    )
    typer.echo(
        f"  Max file  : {shell.max_file_loc} / {shell.limit_file_max} "
        f"{'✅' if shell.file_ok else '❌'}"
    )
    typer.echo(f"  Files     : {shell.file_count}")

    if shell.errors:
        typer.echo(f"  ❌ 超限文件 ({len(shell.errors)}):")
        for f in shell.errors:
            typer.echo(f"    {f.path}: {f.loc} 行 > {shell.limit_file_max}")
    if shell.warnings:
        typer.echo(f"  ⚠️  大文件 ({len(shell.warnings)}):")
        for f in shell.warnings:
            typer.echo(f"    {f.path}: {f.loc} 行 > {shell.limit_file_default}")

    # Scripts Metrics
    if report.scripts:
        scripts = report.scripts
        typer.echo("\n=== Scripts Metrics ===")
        typer.echo(f"  Total LOC : {scripts.total_loc}")
        typer.echo(f"  Max file  : {scripts.max_file_loc}")
        typer.echo(f"  Files     : {scripts.file_count}")

    # Python Metrics
    typer.echo("\n=== Python Metrics ===")
    typer.echo(
        f"  Total LOC : {python.total_loc} / {python.limit_total} "
        f"{'✅' if python.total_ok else '❌'}"
    )
    typer.echo(
        f"  Max file  : {python.max_file_loc} / {python.limit_file_max} "
        f"{'✅' if python.file_ok else '❌'}"
    )
    typer.echo(f"  Files     : {python.file_count}")

    if python.errors:
        typer.echo(f"  ❌ 超限文件 ({len(python.errors)}):")
        for f in python.errors:
            typer.echo(f"    {f.path}: {f.loc} 行 > {python.limit_file_max}")
    if python.warnings:
        typer.echo(f"  ⚠️  大文件 ({len(python.warnings)}):")
        for f in python.warnings:
            typer.echo(f"    {f.path}: {f.loc} 行 > {python.limit_file_default}")

    # Python 分层展示
    if python.subdirs:
        typer.echo("\n  By Directory:")
        for subdir in python.subdirs:
            typer.echo(
                f"    {subdir.name + '/':<14}: {subdir.loc:>5} LOC, "
                f"{subdir.file_count:>2} files, max {subdir.max_file_loc}"
            )

    # Dead Functions Warning
    if report.dead_functions:
        typer.echo("\n=== Dead Functions Warning ===")
        typer.echo(f"  Potentially unused functions ({len(report.dead_functions)}):")
        for df in report.dead_functions:
            typer.echo(f"    {df.name} in {df.file}")
        typer.echo(
            "\n  Note: Some functions may be entry points or used via reflection"
        )


@app.command()
def structure(
    file: Annotated[str, typer.Argument(help="File to analyze")] = "",
    json_out: _JSON_OPT = False,
    trace: _TRACE_OPT = False,
) -> None:
    """Show file structure analysis (functions, LOC, dependencies)."""
    if trace:
        enable_trace()

    if file:
        result = structure_service.analyze_file(file)

        # 添加依赖关系分析（仅 Python 文件）
        if file.endswith(".py"):
            # 提取 imports
            result.imports = dag_service._extract_imports(file)

            # 计算反向依赖（谁导入了我）
            module_graph = dag_service.build_module_graph()
            current_module = dag_service._file_to_module(file)

            # 构建反向依赖映射
            imported_by: list[str] = []
            for module, node in module_graph.items():
                if current_module in node.imports:
                    imported_by.append(module)
            result.imported_by = sorted(imported_by)

        if json_out:
            typer.echo(json.dumps(result.model_dump(), indent=2))
        else:
            typer.echo(f"=== Structure: {file} ===")
            typer.echo(f"  Language  : {result.language}")
            typer.echo(f"  Total LOC : {result.total_loc}")
            typer.echo(f"  Functions : {result.function_count}")
            for fn in result.functions:
                typer.echo(f"    L{fn.line:4d}  {fn.name}  ({fn.loc} lines)")

            # 显示依赖关系
            if result.imports:
                typer.echo(f"\n  Imports ({len(result.imports)}):")
                for imp in result.imports:
                    typer.echo(f"    - {imp}")

            if result.imported_by:
                typer.echo(f"\n  Imported by ({len(result.imported_by)}):")
                for imp_by in result.imported_by:
                    typer.echo(f"    - {imp_by}")
    else:
        # 分析整个 src/vibe3 目录
        from pathlib import Path

        results = []
        for p in sorted(Path("src/vibe3").glob("**/*.py")):
            if "__pycache__" in str(p):
                continue
            # Fail-fast: 不允许静默失败
            file_struct = structure_service.analyze_python_file(str(p))
            results.append(file_struct.model_dump())

        if json_out:
            typer.echo(json.dumps(results, indent=2))
        else:
            typer.echo("=== Python Structure Summary ===")
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
        typer.echo("Available commands: flow, task, pr, inspect, review")
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
