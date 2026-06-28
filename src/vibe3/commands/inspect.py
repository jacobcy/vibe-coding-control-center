"""Evidence-only inspect command group."""

import json
from pathlib import Path
from typing import Annotated

import typer
import yaml

from vibe3.analysis import inspect_python_file
from vibe3.commands.common import enable_method_trace
from vibe3.commands.inspect_base import register as register_base
from vibe3.commands.inspect_symbols import register as register_symbols

app = typer.Typer(
    name="inspect",
    help="""Validated code-review evidence.

Subcommands:
  base [<branch>]            Exact Git changes and Review Kernel evidence
  files <file.py>            Syntax evidence for one Python file
  symbols <file>:<symbol>    Validated positive symbol references

The command does not predict runtime impact, score risk, or decide dead code.
""",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

_JSON_OPT = Annotated[bool, typer.Option("--json", help="Output as JSON")]
_TRACE_OPT = Annotated[
    bool, typer.Option("--trace", help="Enable call tracing (set VIBE3_TRACE=1)")
]

register_symbols(app)
register_base(app)


@app.command(name="files")
def files_(
    file: Annotated[str, typer.Argument(help="Single Python file to inspect")],
    json_out: _JSON_OPT = False,
    yaml_out: Annotated[bool, typer.Option("--yaml", help="Output as YAML")] = False,
    quiet: Annotated[
        bool, typer.Option("--quiet", help="Suppress next step suggestions")
    ] = False,
    trace: _TRACE_OPT = False,
) -> None:
    """Show syntax evidence for a single Python file."""
    from vibe3.clients import GitClient

    del quiet
    if trace:
        enable_method_trace()
    repo_root = Path(GitClient().get_worktree_root())
    input_path = Path(file)
    if not input_path.is_absolute():
        input_path = repo_root / input_path
    result = inspect_python_file(input_path, repo_root=repo_root)

    if json_out:
        typer.echo(result.model_dump_json(indent=2))
    elif yaml_out:
        payload = json.loads(result.model_dump_json())
        typer.echo(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True))
    else:
        typer.echo(f"Observation status: {result.status}")
        if result.file is not None and result.metrics is not None:
            typer.echo(f"=== File: {result.file.path} ===")
            typer.echo(f"  Content SHA256: {result.file.content_sha256}")
            typer.echo(f"  Total lines: {result.metrics.total_lines}")
            typer.echo(f"  Declarations: {len(result.declarations)}")
            for declaration in result.declarations:
                typer.echo(
                    f"    L{declaration.range.start_line}-"
                    f"{declaration.range.end_line} "
                    f"{declaration.kind} {declaration.qualified_name}"
                )
            typer.echo(f"  Direct imports: {len(result.imports)}")
        for diagnostic in result.diagnostics:
            typer.echo(f"  {diagnostic.code}: {diagnostic.message}")

    if result.status != "ready":
        raise typer.Exit(1)
