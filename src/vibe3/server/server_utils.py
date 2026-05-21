"""Server utility functions for orchestra."""

from __future__ import annotations

import socket

import typer


def ensure_port_available(port: int) -> None:
    """Raise typer.Exit if port is already in use."""
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


def find_available_port(
    start_port: int,
    max_port: int | None = None,
) -> tuple[int, bool]:
    """Find an available port in [start_port, max_port].

    Returns (port, was_auto_discovered).
    - (start_port, False) if start_port is available
    - (next_port, True) if start_port is occupied but another port is found
    Raises typer.Exit(1) if no port in range is available.
    """
    if max_port is None:
        max_port = start_port + 10

    for port in range(start_port, max_port + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("0.0.0.0", port))
                return (port, port != start_port)
            except OSError as e:
                if e.errno not in (48, 98):  # Not address-in-use error
                    raise
                # Port is occupied, continue to next port
                continue

    # All ports in range are occupied
    typer.echo(
        f"\n[bold red]Error:[/] All ports from {start_port}"
        f" to {max_port} are already in use.",
        err=True,
    )
    typer.echo(
        "Check if other Orchestra services are running,"
        " or specify a different base port with [bold]--port[/].\n",
        err=True,
    )
    raise typer.Exit(1)
