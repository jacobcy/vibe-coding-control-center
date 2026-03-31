"""Prompt check command - validate and preview prompt recipes."""

from __future__ import annotations

import json
from typing import Annotated, Optional

import typer

from vibe3.prompts.template_loader import load_prompt_templates
from vibe3.prompts.validation import PromptValidationService

app = typer.Typer(
    name="prompt",
    help="Inspect and validate prompt templates and recipes",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def _flatten_template_keys(templates: object, prefix: str = "") -> list[str]:
    """Recursively collect all leaf template keys from a nested dict."""
    if not isinstance(templates, dict):
        return [prefix] if prefix else []
    keys: list[str] = []
    for k, v in templates.items():
        full = f"{prefix}.{k}" if prefix else k
        if isinstance(v, str):
            keys.append(full)
        elif isinstance(v, dict):
            keys.extend(_flatten_template_keys(v, full))
    return sorted(keys)


@app.command()
def check(
    template_key: Annotated[
        Optional[str],
        typer.Argument(help="Dotted template key to check (e.g. run.plan)"),
    ] = None,
    output_json: Annotated[
        bool,
        typer.Option("--json", help="Output result as JSON"),
    ] = False,
    list_all: Annotated[
        bool,
        typer.Option("--list", help="List all known template keys"),
    ] = False,
) -> None:
    """Validate a prompt template key and show required variables.

    Check that a template key exists in prompts.yaml and report which
    variables the template requires.  Use --list to enumerate all keys.

    Examples:

      vibe3 prompt check run.plan

      vibe3 prompt check run.plan --json

      vibe3 prompt check --list
    """
    if list_all:
        _run_list(output_json)
        return

    if not template_key:
        typer.echo("Error: provide TEMPLATE_KEY or --list", err=True)
        raise typer.Exit(1)

    _run_check(template_key, output_json)


def _run_list(output_json: bool) -> None:
    keys = _flatten_template_keys(load_prompt_templates())
    if output_json:
        typer.echo(json.dumps(keys))
    else:
        typer.echo("Known template keys:")
        for key in keys:
            typer.echo(f"  {key}")


def _run_check(template_key: str, output_json: bool) -> None:
    svc = PromptValidationService()
    result = svc.validate_template_key(template_key)

    if output_json:
        data = {
            "template_key": result.template_key,
            "is_valid": result.is_valid,
            "required_variables": sorted(result.required_variables),
            "issues": [{"kind": i.kind, "message": i.message} for i in result.issues],
        }
        typer.echo(json.dumps(data))
        if not result.is_valid:
            raise typer.Exit(1)
        return

    if not result.is_valid:
        for issue in result.issues:
            typer.echo(f"Error: {issue.message}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Template key: {template_key}")
    typer.echo(f"Required variables: {', '.join(sorted(result.required_variables))}")
    typer.echo("OK")
