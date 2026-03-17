"""structure 命令 - 分析文件结构."""

import json
from contextlib import contextmanager
from typing import Annotated, Iterator

import typer
from loguru import logger
from rich import print as rprint

from vibe3.observability.logger import setup_logging
from vibe3.observability.trace import trace_context
from vibe3.services.structure_service import StructureError, analyze_file

app = typer.Typer(help="分析文件结构")


@contextmanager
def _noop() -> Iterator[None]:
    yield


@app.command()
def show(
    file_path: Annotated[str, typer.Argument(help="文件路径")],
    json_output: Annotated[bool, typer.Option("--json", help="JSON 输出")] = False,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
) -> None:
    """分析并显示文件结构."""
    if trace:
        setup_logging(verbose=2)

    ctx = (
        trace_context(command="structure show", domain="structure", file=file_path)
        if trace
        else _noop()
    )
    with ctx:
        logger.bind(domain="structure", action="show", file=file_path).info(
            "Running structure show"
        )

        try:
            result = analyze_file(file_path)

            if json_output:
                typer.echo(json.dumps(result.model_dump(), indent=2))
                return

            rprint(f"\n[bold]{result.path}[/bold] ({result.language})")
            rprint(f"  总行数: {result.total_loc}")
            rprint(f"  函数数: {result.function_count}")

            if result.functions:
                rprint("  函数列表:")
                for f in result.functions:
                    rprint(f"    L{f.line:>4}  {f.name}  ({f.loc} 行)")

        except StructureError as e:
            rprint(f"[red]Error:[/red] {e.message}")
            raise typer.Exit(1)
