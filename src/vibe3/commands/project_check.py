"""Project check command implementation."""

import json
from typing import Annotated

import typer
from rich.console import Console

from vibe3.services.project_check_service import (
    ProjectCheckResult,
    ProjectCheckService,
)

app = typer.Typer(
    help="Check vibe3 ecosystem project environment",
    rich_markup_mode="rich",
)


def _render_status(status: str) -> str:
    """Render status with color."""
    if status == "pass":
        return "[green]✓[/green]"
    elif status == "fail":
        return "[red]✗[/red]"
    elif status == "warning":
        return "[yellow]⚠[/yellow]"
    else:  # skip
        return "[dim]○[/dim]"


def _render_result_console(result: ProjectCheckResult, verbose: bool) -> None:
    """Render result to console with rich formatting.

    Args:
        result: Project check result
        verbose: If True, show all items; otherwise show only fail/warning
    """
    console = Console()

    # Header
    console.print("\n[bold]Project Environment Check[/bold]")
    console.print("=" * 40 + "\n")

    # Render each category
    for category in result.categories:
        console.print(f"  [bold]{category.name}[/bold]")

        for item in category.items:
            # Skip pass items in non-verbose mode
            if not verbose and item.status == "pass":
                continue

            status_icon = _render_status(item.status)
            message = item.message

            # Add detail in verbose mode or for non-pass items
            if verbose and item.detail:
                console.print(f"    {status_icon} {message}")
                console.print(f"      [dim]{item.detail}[/dim]")
            else:
                console.print(f"    {status_icon} {message}")

        console.print()  # Empty line after category

    # Summary
    counts = result.count_results()
    summary_parts = []
    if counts["fail"] > 0:
        summary_parts.append(f"[red]{counts['fail']} FAILED[/red]")
    if counts["warning"] > 0:
        summary_parts.append(f"[yellow]{counts['warning']} WARNING[/yellow]")
    if counts["pass"] > 0:
        summary_parts.append(f"[green]{counts['pass']} PASSED[/green]")
    if counts["skip"] > 0:
        summary_parts.append(f"[dim]{counts['skip']} SKIPPED[/dim]")

    console.print(f"[bold]Result:[/bold] {', '.join(summary_parts)}")

    if not verbose and counts["pass"] > 0:
        console.print("\n  [dim]Run with --verbose for full details[/dim]")

    console.print()


def _render_result_json(result: ProjectCheckResult) -> str:
    """Render result as JSON.

    Args:
        result: Project check result

    Returns:
        JSON string
    """
    output: dict[str, object] = {
        "overall": result.overall,
        "categories": [],
        "summary": result.count_results(),
    }

    for category in result.categories:
        cat_data: dict[str, object] = {
            "name": category.name,
            "items": [],
        }
        for item in category.items:
            items_list = cat_data["items"]
            if isinstance(items_list, list):
                items_list.append(
                    {
                        "name": item.name,
                        "status": item.status,
                        "message": item.message,
                        "detail": item.detail,
                        "fixable": item.fixable,
                    }
                )
        categories_list = output["categories"]
        if isinstance(categories_list, list):
            categories_list.append(cat_data)

    return json.dumps(output, indent=2)


@app.callback(invoke_without_command=True)
def check(
    ctx: typer.Context,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Show all check items (including passing ones)",
        ),
    ] = False,
    fix: Annotated[
        bool,
        typer.Option(
            "--fix",
            help="Automatically fix fixable issues",
        ),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Output in JSON format (for CI/CD integration)",
        ),
    ] = False,
) -> None:
    """Check vibe3 ecosystem project environment.

    This command validates the project environment for vibe3 ecosystem projects,
    covering 5 major categories:

    - [bold]Git Repository[/bold]: Repository status, remote, branches
    - [bold]vibe3 Configuration[/bold]: Config directories and files
    - [bold]Dependencies[/bold]: Project manifest, tools, Python version
    - [bold]Orchestra Configuration[/bold]: Settings, repo config, base ref
    - [bold]GitHub Integration[/bold]: gh CLI, authentication, permissions

    [green]Examples:[/green]

      [cyan]vibe3 project-check[/cyan]
      Check project environment (show only failures and warnings)

      [cyan]vibe3 project-check --verbose[/cyan]
      Show all check items including passing ones

      [cyan]vibe3 project-check --fix[/cyan]
      Automatically fix fixable issues (e.g., create missing directories)

      [cyan]vibe3 project-check --json[/cyan]
      Output in JSON format for CI/CD integration
    """
    # Mutual exclusion: --json and --verbose
    if json_output and verbose:
        typer.echo(
            "Error: --json and --verbose are mutually exclusive",
            err=True,
        )
        raise typer.Exit(code=1)

    try:
        service = ProjectCheckService()
        result = service.run_checks(fix=fix)

        if json_output:
            json_str = _render_result_json(result)
            typer.echo(json_str)
        else:
            _render_result_console(result, verbose=verbose)

        # Exit code: 0 if all pass, 1 if any fail
        # Use raise_system_exit to avoid "Error:" message
        if not result.overall:
            raise typer.Exit(code=1)

    except typer.Exit:
        # Re-raise typer.Exit to preserve exit code
        raise
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
