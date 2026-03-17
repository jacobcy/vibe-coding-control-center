"""metrics 命令 - 查看代码量指标."""

import json
from contextlib import contextmanager
from typing import Annotated, Iterator

import typer
from loguru import logger
from rich import print as rprint

from vibe3.observability.logger import setup_logging
from vibe3.observability.trace import trace_context
from vibe3.services.metrics_service import LayerMetrics, MetricsError, collect_metrics

app = typer.Typer(help="查看代码量指标")


@contextmanager
def _noop() -> Iterator[None]:
    yield


def _render_layer(name: str, m: LayerMetrics) -> None:
    """渲染单层指标."""
    status = "✅" if m.total_ok and m.file_ok else "❌"
    rprint(f"\n[bold]{name}[/bold] {status}")
    rprint(f"  总行数: {m.total_loc} / {m.limit_total}")
    rprint(f"  最大文件: {m.max_file_loc} / {m.limit_file} 行")
    rprint(f"  文件数: {m.file_count}")

    if m.violations:
        rprint(f"  [red]超限文件 ({len(m.violations)}):[/red]")
        for f in m.violations:
            rprint(f"    {f.path}: {f.loc} 行")


@app.command()
def show(
    json_output: Annotated[bool, typer.Option("--json", help="JSON 输出")] = False,
    trace: Annotated[bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")] = False,  # noqa: E501
) -> None:
    """显示代码量指标."""
    if trace:
        setup_logging(verbose=2)

    ctx = trace_context(command="metrics show", domain="metrics") if trace else _noop()
    with ctx:
        log = logger.bind(domain="metrics", action="show")
        log.info("Running metrics show")

        try:
            report = collect_metrics()

            if json_output:
                typer.echo(json.dumps(report.model_dump(), indent=2))
                return

            _render_layer("Shell (v2)", report.shell)
            _render_layer("Python (v3)", report.python)

        except MetricsError as e:
            rprint(f"[red]Error:[/red] {e.message}")
            raise typer.Exit(1)
