#!/usr/bin/env python3
"""Task command handlers."""
import typer
from rich import print

app = typer.Typer(help="Manage execution tasks")


@app.command()
def list() -> None:
    """List all tasks."""
    print("[cyan]Tasks:[/] No tasks found")


@app.command()
def show(
    task_id: str = typer.Argument(..., help="Task ID")
) -> None:
    """Show task details."""
    print(f"[cyan]Task:[/] {task_id}")


@app.command()
def link(
    task_id: str = typer.Argument(..., help="Task ID"),
    flow: str = typer.Option(..., help="Flow to link")
) -> None:
    """Link task to a flow."""
    print(f"[green]Linked task[/] {task_id} [green]to flow[/] {flow}")