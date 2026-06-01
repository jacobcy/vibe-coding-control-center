"""Status command - system status dashboard."""

import json
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Annotated

import typer

from vibe3.commands import _validate_pid_file
from vibe3.commands.command_options import (
    FormatOption,
    TraceMinMsOption,
    TraceOption,
)
from vibe3.commands.common import (
    enable_method_trace,
    run_full_check_shortcut,
    validate_trace_options,
)
from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.services.orchestra_helpers import get_manager_usernames
from vibe3.services.orchestra_status_service import OrchestraStatusService
from vibe3.ui.console import console
from vibe3.utils.time_format import format_age_aware_time


def _resolve_server_label(
    config: OrchestraConfig, snapshot_found: bool, server_running: bool
) -> str:
    if snapshot_found and server_running:
        return "[green]running[/]"
    pid, is_valid = _validate_pid_file(config.pid_file)
    if is_valid and pid is not None:
        return "[green]running[/]"
    return "[dim]stopped[/]"


def _compute_effective_server_running(
    snapshot_running: bool, config: OrchestraConfig
) -> bool:
    """Unified server status: snapshot is authoritative, PID-valid is fallback."""
    if snapshot_running:
        return True
    _, pid_valid = _validate_pid_file(config.pid_file)
    return pid_valid


def _resolve_repo_name(config_repo: str | None) -> str:
    """Resolve repo name from config or fallback to git remote URL."""
    if config_repo:
        return config_repo
    try:
        import subprocess

        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        url = result.stdout.strip()
        if url.startswith("git@github.com:"):
            return url.split(":")[-1].removesuffix(".git")
        if "github.com" in url:
            return url.split("/")[-2] + "/" + url.split("/")[-1].removesuffix(".git")
    except Exception:
        pass
    return "(unknown)"


def _render_configuration(config: OrchestraConfig) -> None:
    """Render Vibe3 configuration section in status output."""
    manager = ", ".join(get_manager_usernames(config))
    console.print("[bold]Vibe3 Configuration[/]")
    console.print(f"  Repo:              {_resolve_repo_name(config.repo)}")
    console.print(f"  Manager agents:    {manager}")
    console.print(f"  Max concurrent:    {config.max_concurrent_flows}")
    console.print(f"  Polling interval:  {config.polling_interval}s")
    console.print(f"  Scene base ref:    {config.scene_base_ref}")
    console.print()


def show_system_status(
    check: Annotated[
        bool,
        typer.Option("--check", help="显示前先运行完整 vibe3 check"),
    ] = False,
    output_format: FormatOption = "table",
    trace: TraceOption = False,
    min_ms: TraceMinMsOption = None,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="[DEPRECATED] Use --format json instead",
            hidden=True,
        ),
    ] = False,
) -> None:
    """Show system status: Orchestra status and Vibe3 configuration."""
    validate_trace_options(trace, min_ms)
    if trace:
        enable_method_trace(min_ms=min_ms)

    if json_output and output_format == "table":
        typer.echo(
            "Warning: --json is deprecated, use --format json instead",
            err=True,
        )
        output_format = "json"
    if check:
        run_full_check_shortcut()

    import time

    config = load_orchestra_config()
    orch_snapshot = OrchestraStatusService.fetch_live_snapshot(config)
    if orch_snapshot is None:
        time.sleep(0.5)
        orch_snapshot = OrchestraStatusService.fetch_live_snapshot(config)
    snapshot_found = orch_snapshot is not None

    if not orch_snapshot:
        _, pid_alive = _validate_pid_file(config.pid_file)
        if pid_alive:
            import time

            time.sleep(0.5)
            orch_snapshot = OrchestraStatusService.fetch_live_snapshot(config)
            snapshot_found = orch_snapshot is not None

    if not orch_snapshot:
        from dataclasses import replace

        from vibe3.services.flow_orchestrator_service import (
            FlowOrchestratorService,
        )

        orch_service = OrchestraStatusService(
            config, orchestrator=FlowOrchestratorService(config)
        )
        local_snap = orch_service.snapshot()
        orch_snapshot = replace(local_snap, server_running=False)

    # JSON/YAML output
    if output_format in ("json", "yaml"):
        output_data = {
            "orchestra": asdict(orch_snapshot),
            "config": {
                "repo": _resolve_repo_name(config.repo),
                "manager_usernames": get_manager_usernames(config),
                "max_concurrent_flows": config.max_concurrent_flows,
                "polling_interval": config.polling_interval,
                "scene_base_ref": config.scene_base_ref,
            },
        }
        if output_format == "json":
            typer.echo(json.dumps(output_data, indent=2))
        else:
            from yaml import safe_dump

            typer.echo(safe_dump(output_data, default_flow_style=False))
        return

    # Table output
    timestamp = format_age_aware_time(
        datetime.fromtimestamp(orch_snapshot.timestamp, tz=timezone.utc)
    )
    console.print(f"[bold]Orchestra Status[/] ({timestamp})")
    server_label = _resolve_server_label(
        config, snapshot_found, orch_snapshot.server_running
    )
    console.print(f"Server: {server_label}")
    if orch_snapshot.active_flows > 0:
        console.print(
            f"Active flows: [green]{orch_snapshot.active_flows}[/] "
            f"({orch_snapshot.active_worktrees} worktrees)"
        )
    elif not _compute_effective_server_running(orch_snapshot.server_running, config):
        console.print("Dispatch: [dim]inactive (server stopped)[/]")
    else:
        console.print("Dispatch: [green]active[/]")

    if orch_snapshot.queued_issues:
        console.print(
            f"Queue: [yellow]{len(orch_snapshot.queued_issues)} issues waiting[/]"
        )
    console.print()

    _render_configuration(config)

    console.print(
        "\n[dim]Use `vibe3 task status` to view issue progress and ready queue.[/]"
    )
