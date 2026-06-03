"""Status command - unified dashboard for flows and orchestra."""

import json
from dataclasses import asdict
from datetime import timezone
from typing import TYPE_CHECKING, Annotated

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
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.orchestra.logging import orchestra_events_log_path
from vibe3.services.orchestra_helpers import get_manager_usernames
from vibe3.ui.console import console
from vibe3.utils.time_format import format_age_aware_time

if TYPE_CHECKING:
    from vibe3.services.orchestra_status_service import OrchestraSnapshot


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


def _render_system_status(
    config: OrchestraConfig,
    orch_snapshot: "OrchestraSnapshot",
    snapshot_found: bool,
) -> None:
    """Render Orchestra Status and Vibe3 Configuration sections only."""
    from datetime import datetime

    ts_utc = datetime.fromtimestamp(orch_snapshot.timestamp, tz=timezone.utc)
    ts_str = format_age_aware_time(ts_utc)
    console.print(f"[bold]Orchestra Status[/] [dim]({ts_str})[/]")
    console.print(
        "Server: "
        + _resolve_server_label(config, snapshot_found, orch_snapshot.server_running)
    )
    console.print(f"Log: {orchestra_events_log_path()}")

    if orch_snapshot.dispatch_blocked:
        console.print(
            "Dispatch: [bold red]FROZEN[/] " f"[dim]({orch_snapshot.blocked_reason})[/]"
        )
        if orch_snapshot.blocked_issue_number is not None:
            console.print(f"  [red]Issue:   #{orch_snapshot.blocked_issue_number}[/]")
        console.print(f"  [red]Reason:  {orch_snapshot.blocked_issue_reason}[/]")
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


def _full_status_dashboard(
    all_flows: bool = False,
    check: bool = False,
    output_format: str = "table",
    trace: bool = False,
    min_ms: int | None = None,
) -> None:
    """Render full task status dashboard (system status + all progress panels)."""
    validate_trace_options(trace, min_ms)
    if trace:
        enable_method_trace(min_ms=min_ms)

    from vibe3.commands.status_render import (
        render_blocked_items,
        render_completed_flows,
        render_epic_items,
        render_issue_progress,
        render_missing_state_items,
        render_pr_ref_items,
        render_remote_items,
        render_rfc_items,
        render_supervisor_issues,
    )
    from vibe3.services.task_status_service import (
        classify_task_issues_for_rendering,
        fetch_task_status_data,
    )

    if check:
        run_full_check_shortcut()

    # Fetch all data via service layer
    data = fetch_task_status_data(all_flows=all_flows)

    # Handle JSON/YAML output
    if output_format in ("json", "yaml"):
        output_data = {
            "orchestra": asdict(data.orch_snapshot),
            "flows": [f.model_dump() for f in data.flows],
            "orchestrated_issues": data.orchestrated_issues,
        }

        if output_format == "json":
            typer.echo(json.dumps(output_data, indent=2, default=str))
        else:  # yaml
            import yaml

            typer.echo(
                yaml.dump(output_data, default_flow_style=False, allow_unicode=True)
            )
        return

    # Render system status
    _render_system_status(data.config, data.orch_snapshot, data.snapshot_found)

    # Classify issues for rendering
    classified = classify_task_issues_for_rendering(
        data.orchestrated_issues, data.config
    )

    # Render all progress panels
    render_issue_progress(classified["bucketed_items"], data.config)
    console.print()

    render_remote_items(classified["remote_items"])
    console.print()

    render_supervisor_issues(classified["supervisor_items"])
    console.print()

    render_pr_ref_items(classified["pr_ref_items"])

    render_missing_state_items(
        classified["waiting_for_pool_items"], classified["governed_anomaly_items"]
    )
    render_rfc_items(classified["roadmap_rfc_items"])
    render_epic_items(classified["roadmap_epic_items"], data.orchestrated_issues)
    render_blocked_items(classified["blocked_items"])

    if all_flows:
        completed_flows = [
            flow
            for flow in data.flows
            if getattr(flow, "flow_status", "active") in {"done", "aborted", "merged"}
        ]
        render_completed_flows(completed_flows)


def status(
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
    """Show orchestra system status and configuration only."""
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

    from vibe3.config.orchestra_settings import load_orchestra_config
    from vibe3.services.flow_orchestrator_service import FlowOrchestratorService
    from vibe3.services.orchestra_status_service import OrchestraStatusService

    # Fetch config and snapshot only (no flows or issues)
    config = load_orchestra_config()
    orch_snapshot = OrchestraStatusService.fetch_live_snapshot(config)
    if orch_snapshot is None:
        time.sleep(0.5)
        orch_snapshot = OrchestraStatusService.fetch_live_snapshot(config)
    snapshot_found = orch_snapshot is not None

    if not orch_snapshot:
        _, pid_alive = _validate_pid_file(config.pid_file)
        if pid_alive:
            time.sleep(0.5)
            orch_snapshot = OrchestraStatusService.fetch_live_snapshot(config)
            snapshot_found = orch_snapshot is not None

    if not orch_snapshot:
        from dataclasses import replace

        orch_service = OrchestraStatusService(
            config, orchestrator=FlowOrchestratorService(config)
        )
        local_snap = orch_service.snapshot()
        orch_snapshot = replace(local_snap, server_running=False)

    # Assert orch_snapshot is non-None after fallback
    assert orch_snapshot is not None

    # Handle JSON/YAML output (system status only)
    if output_format in ("json", "yaml"):
        output_data = {
            "orchestra": asdict(orch_snapshot),
        }

        if output_format == "json":
            typer.echo(json.dumps(output_data, indent=2, default=str))
        else:  # yaml
            import yaml

            typer.echo(
                yaml.dump(output_data, default_flow_style=False, allow_unicode=True)
            )
        return

    # Render system status only
    _render_system_status(config, orch_snapshot, snapshot_found)

    # Print hint
    typer.echo(
        "Use 'vibe3 task status' to view issue progress and ready queue",
        err=True,
    )
