"""Inspect command - 信息提供层，输出结构化数据供 vibe review 消费."""

import json
from typing import Annotated

import typer

from vibe3.commands.inspect_helpers import build_change_analysis, enable_trace
from vibe3.services import (
    command_analyzer,
    metrics_service,
    structure_service,
)
from vibe3.services.serena_service import SerenaService

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
    typer.echo("=== Shell Metrics ===")
    typer.echo(
        f"  Total LOC : {shell.total_loc} / {shell.limit_total} "
        f"{'✅' if shell.total_ok else '❌'}"
    )
    typer.echo(
        f"  Max file  : {shell.max_file_loc} / {shell.limit_file} "
        f"{'✅' if shell.file_ok else '❌'}"
    )
    typer.echo(f"  Files     : {shell.file_count}")

    typer.echo("\n=== Python Metrics ===")
    typer.echo(
        f"  Total LOC : {python.total_loc} / {python.limit_total} "
        f"{'✅' if python.total_ok else '❌'}"
    )
    typer.echo(
        f"  Max file  : {python.max_file_loc} / {python.limit_file} "
        f"{'✅' if python.file_ok else '❌'}"
    )
    typer.echo(f"  Files     : {python.file_count}")

    if python.violations:
        typer.echo("\n⚠️  Violations:")
        for v in python.violations:
            typer.echo(f"  {v.path}: {v.loc} lines")


@app.command()
def structure(
    file: Annotated[str, typer.Argument(help="File to analyze")] = "",
    json_out: _JSON_OPT = False,
    trace: _TRACE_OPT = False,
) -> None:
    """Show file structure analysis (functions, LOC)."""
    if trace:
        enable_trace()

    if file:
        result = structure_service.analyze_file(file)
        if json_out:
            typer.echo(json.dumps(result.model_dump(), indent=2))
        else:
            typer.echo(f"=== Structure: {file} ===")
            typer.echo(f"  Language  : {result.language}")
            typer.echo(f"  Total LOC : {result.total_loc}")
            typer.echo(f"  Functions : {result.function_count}")
            for fn in result.functions:
                typer.echo(f"    L{fn.line:4d}  {fn.name}  ({fn.loc} lines)")
    else:
        # 分析整个 src/vibe3 目录
        from pathlib import Path

        results = []
        for p in sorted(Path("src/vibe3").glob("**/*.py")):
            if "__pycache__" in str(p):
                continue
            try:
                file_struct = structure_service.analyze_python_file(str(p))
                results.append(file_struct.model_dump())
            except Exception:
                pass

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
def symbols(
    file: Annotated[str, typer.Argument(help="File or directory to analyze")] = ".",
    json_out: _JSON_OPT = False,
    trace: _TRACE_OPT = False,
) -> None:
    """Show code symbols (functions, classes, references).

    Examples:
        vibe inspect symbols
        vibe inspect symbols src/vibe3/services/flow_service.py
    """
    if trace:
        enable_trace()

    svc = SerenaService()
    result = svc.analyze_file(file)

    if json_out:
        typer.echo(json.dumps(result, indent=2))
        return

    typer.echo(f"=== Symbols: {file} ===")
    typer.echo(f"  Status  : {result['status']}")
    for sym in result.get("symbols", []):
        refs = sym.get("references", 0)
        typer.echo(f"  {sym['name']}  ({refs} refs)")


@app.command()
def commands(
    command: Annotated[str, typer.Argument(help="Command name")] = "",
    subcommand: Annotated[str, typer.Argument(help="Subcommand name")] = "",
    json_out: _JSON_OPT = False,
    trace: _TRACE_OPT = False,
) -> None:
    """Show vibe command structure (static analysis, no execution).

    Examples:
        vibe inspect commands
        vibe inspect commands review
        vibe inspect commands review pr
    """
    if trace:
        enable_trace()

    if not command:
        typer.echo("Available commands: flow, task, pr, inspect, review")
        return

    result = command_analyzer.analyze_command(command, subcommand or None)

    if json_out:
        typer.echo(json.dumps(result.model_dump(), indent=2))
        return

    typer.echo(f"=== Call Chain: vibe {result.command} ===")
    typer.echo(f"  File  : {result.file_path}")
    typer.echo(f"  Depth : {result.call_depth}")
    for edge in result.calls:
        typer.echo(f"  L{edge.line:4d}  {edge.caller} → {edge.callee}")


@app.command()
def pr(
    pr_number: Annotated[int, typer.Argument(help="PR number")],
    json_out: _JSON_OPT = False,
    trace: _TRACE_OPT = False,
) -> None:
    """PR change analysis (serena + dag + scoring).

    Example: vibe inspect pr 42
    """
    if trace:
        enable_trace()

    result = build_change_analysis("pr", str(pr_number))

    if json_out:
        typer.echo(json.dumps(result, indent=2, default=str))
        return

    score = result["score"]
    assert isinstance(score, dict)
    typer.echo(f"=== PR #{pr_number} Analysis ===")
    typer.echo(f"  Changed files    : {len(result['impact'].get('changed_files', []))}")  # type: ignore
    typer.echo(f"  Impacted modules : {len(result['dag']['impacted_modules'])}")  # type: ignore
    typer.echo(f"  Risk score       : {score['score']} ({score['level']})")
    typer.echo(f"  Block            : {score['block']}")


@app.command()
def commit(
    sha: Annotated[str, typer.Argument(help="Commit SHA")],
    json_out: _JSON_OPT = False,
    trace: _TRACE_OPT = False,
) -> None:
    """Commit change analysis.

    Example: vibe inspect commit HEAD~1
    """
    if trace:
        enable_trace()

    result = build_change_analysis("commit", sha)

    if json_out:
        typer.echo(json.dumps(result, indent=2, default=str))
        return

    score = result["score"]
    assert isinstance(score, dict)
    typer.echo(f"=== Commit {sha} Analysis ===")
    typer.echo(f"  Changed files    : {len(result['impact'].get('changed_files', []))}")  # type: ignore
    typer.echo(f"  Impacted modules : {len(result['dag']['impacted_modules'])}")  # type: ignore
    typer.echo(f"  Risk score       : {score['score']} ({score['level']})")


@app.command()
def base(
    branch: Annotated[str, typer.Argument(help="Branch to compare against main")],
    json_out: _JSON_OPT = False,
    trace: _TRACE_OPT = False,
) -> None:
    """Branch change analysis (relative to main).

    Example: vibe inspect base feature/my-branch
    """
    if trace:
        enable_trace()

    result = build_change_analysis("branch", branch)

    if json_out:
        typer.echo(json.dumps(result, indent=2, default=str))
        return

    score = result["score"]
    assert isinstance(score, dict)
    typer.echo(f"=== Branch {branch} Analysis ===")
    typer.echo(f"  Changed files    : {len(result['impact'].get('changed_files', []))}")  # type: ignore
    typer.echo(f"  Impacted modules : {len(result['dag']['impacted_modules'])}")  # type: ignore
    typer.echo(f"  Risk score       : {score['score']} ({score['level']})")
