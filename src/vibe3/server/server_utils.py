"""Server utility functions for orchestra."""

from __future__ import annotations

import typer


def ensure_port_available(port: int) -> None:
    """Raise typer.Exit if port is already in use."""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            # Use SO_REUSEADDR to be consistent with common server behavior
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("0.0.0.0", port))
        except OSError as e:
            if e.errno in (48, 98):  # MacOS: 48, Linux: 98
                typer.echo(
                    f"\n[bold red]Error:[/] Port {port} is already in use.",
                    err=True,
                )
                typer.echo(
                    "Check if another Orchestra service is running on this port.",
                    err=True,
                )
                typer.echo(
                    "Use [bold]vibe3 serve stop[/] or specify [bold]--port[/].\n",
                    err=True,
                )
                raise typer.Exit(1)
            raise
