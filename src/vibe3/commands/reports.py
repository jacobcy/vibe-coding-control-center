"""Reports command implementation - manage .agent/reports/ cleanup."""

import json
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from vibe3.services.report_cleanup_service import ReportCleanupService

app = typer.Typer(
    help="Manage reports cleanup and retention",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

console = Console()


@app.command("list")
def list_reports(
    report_type: Annotated[
        str | None,
        typer.Option("--type", "-t", help="Filter by report type"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output in JSON format"),
    ] = False,
) -> None:
    """List all reports with sizes and ages.

    Examples:
        vibe3 reports list
        vibe3 reports list --type pre-push-review
        vibe3 reports list --json
    """
    service = ReportCleanupService()

    if report_type:
        # List specific type
        reports = service.list_reports(report_type)
        if not reports:
            if json_output:
                print(json.dumps([]))
            else:
                console.print(
                    f"[yellow]No reports found for type: " f"{report_type}[/yellow]"
                )
            return

        if json_output:
            data = [
                {
                    "path": str(r.path),
                    "size_bytes": r.size_bytes,
                    "size_kb": round(r.size_kb, 2),
                    "mtime": r.mtime,
                    "age_days": round(r.age_days, 2),
                }
                for r in reports
            ]
            print(json.dumps(data, indent=2))
        else:
            table = Table(title=f"Reports: {report_type}")
            table.add_column("File", style="cyan")
            table.add_column("Size", justify="right", style="green")
            table.add_column("Age", justify="right", style="yellow")

            for report in reports:
                table.add_row(
                    report.path.name,
                    f"{report.size_kb:.1f} KB",
                    report.age_display,
                )

            console.print(table)
    else:
        # List all types
        all_reports: list[dict[str, Any]] = []
        for type_def in service.get_report_types():
            reports = service.list_reports(type_def.name)
            for rpt in reports:
                all_reports.append(
                    {
                        "type": type_def.name,
                        "path": str(rpt.path),
                        "size_bytes": rpt.size_bytes,
                        "size_kb": round(rpt.size_kb, 2),
                        "mtime": rpt.mtime,
                        "age_days": round(rpt.age_days, 2),
                    }
                )

        if json_output:
            print(json.dumps(all_reports, indent=2))
        else:
            table = Table(title="All Reports")
            table.add_column("Type", style="cyan")
            table.add_column("File", style="cyan")
            table.add_column("Size", justify="right", style="green")
            table.add_column("Age", justify="right", style="yellow")

            for report_dict in all_reports:
                table.add_row(
                    report_dict["type"],
                    Path(report_dict["path"]).name,
                    f"{report_dict['size_kb']:.1f} KB",
                    f"{report_dict['age_days']:.1f}d",
                )

            console.print(table)


@app.command("clean")
def clean_reports(
    report_type: Annotated[
        str | None,
        typer.Option("--type", "-t", help="Clean specific report type only"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Preview deletions without executing (default: True)",
        ),
    ] = True,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Actually delete files (required for non-dry-run)",
        ),
    ] = False,
    max_count: Annotated[
        int | None,
        typer.Option("--max-count", help="Override max_count for retention"),
    ] = None,
    max_age_days: Annotated[
        int | None,
        typer.Option("--max-age-days", help="Override max_age_days for retention"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output in JSON format"),
    ] = False,
) -> None:
    """Clean old reports based on retention policy.

    By default, runs in dry-run mode to preview deletions.
    Use --force to actually delete files.

    Examples:
        vibe3 reports clean                    # Dry-run all types
        vibe3 reports clean --force            # Actually clean all types
        vibe3 reports clean --type coverage    # Dry-run specific type
        vibe3 reports clean --type coverage --force  # Clean specific type
        vibe3 reports clean --max-count 5      # Override retention count
    """
    # Safety check: require --force for actual deletion
    if not dry_run and not force:
        console.print(
            "[red]Error: Must use --force to actually delete files. "
            "Default is dry-run mode.[/red]"
        )
        raise typer.Exit(code=1)

    # If --force is set, disable dry_run
    if force:
        dry_run = False

    service = ReportCleanupService()

    if report_type:
        # Clean specific type
        result = service.clean_reports(
            report_type,
            dry_run=dry_run,
            max_count=max_count,
            max_age_days=max_age_days,
        )

        if json_output:
            print(json.dumps(result, indent=2))
        else:
            mode = "Would delete" if dry_run else "Deleted"
            console.print(
                f"\n[cyan]{mode} {result['deleted']} reports[/cyan] "
                f"(kept {result['kept']}, freed {result['freed_bytes'] / 1024:.1f} KB)"
            )

            if dry_run and result["files_deleted"]:
                console.print("\n[yellow]Files to be deleted:[/yellow]")
                for file_path in result["files_deleted"]:
                    console.print(f"  {file_path}")
    else:
        # Clean all types
        results = service.clean_all(dry_run=dry_run)

        if json_output:
            print(json.dumps(results, indent=2))
        else:
            mode = "Would delete" if dry_run else "Deleted"
            total_deleted = sum(r["deleted"] for r in results.values())
            total_freed = sum(r["freed_bytes"] for r in results.values())

            console.print(
                f"\n[cyan]{mode} {total_deleted} reports total[/cyan] "
                f"(freed {total_freed / 1024:.1f} KB)"
            )

            table = Table(title="Cleanup Summary")
            table.add_column("Type", style="cyan")
            table.add_column("Kept", justify="right", style="green")
            table.add_column("Deleted", justify="right", style="red")
            table.add_column("Freed (KB)", justify="right", style="yellow")

            for type_name, result in results.items():
                table.add_row(
                    type_name,
                    str(result["kept"]),
                    str(result["deleted"]),
                    f"{result['freed_bytes'] / 1024:.1f}",
                )

            console.print(table)


@app.command("status")
def status(
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output in JSON format"),
    ] = False,
) -> None:
    """Show disk usage summary for reports directory.

    Examples:
        vibe3 reports status
        vibe3 reports status --json
    """
    service = ReportCleanupService()
    usage = service.get_disk_usage()

    if json_output:
        print(json.dumps(usage, indent=2))
    else:
        console.print("\n[bold]Reports Directory Summary[/bold]")
        console.print(f"  Location: {service.REPORTS_DIR}")
        console.print(f"  Total size: {usage['total_bytes'] / 1024:.1f} KB")
        console.print(f"  Total files: {usage['total_files']}")
        console.print(f"  Total directories: {usage['total_dirs']}")

        # Show per-type breakdown
        console.print("\n[bold]Reports by Type:[/bold]")
        table = Table()
        table.add_column("Type", style="cyan")
        table.add_column("Count", justify="right", style="green")
        table.add_column("Total Size", justify="right", style="yellow")

        for type_def in service.get_report_types():
            reports = service.list_reports(type_def.name)
            if reports:
                total_size = sum(r.size_bytes for r in reports)
                table.add_row(
                    type_def.name,
                    str(len(reports)),
                    f"{total_size / 1024:.1f} KB",
                )

        console.print(table)


if __name__ == "__main__":
    app()
