"""Status command - unified dashboard for flows and orchestra."""

import json
import os
import subprocess
from dataclasses import asdict
from datetime import timezone
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

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
from vibe3.config import OVERRIDE_RULES, get_manager_usernames
from vibe3.models import OrchestraConfig
from vibe3.observability import orchestra_events_log_path
from vibe3.server import validate_pid_file
from vibe3.ui import console
from vibe3.utils import format_age_aware_time

if TYPE_CHECKING:
    from vibe3.services.orchestra import OrchestraSnapshot

# Issue #3189: review/failed are PR-backed terminal states shown in completed.
# "merged" is a historical status migrated to "done" by FlowState.
COMPLETED_FLOW_STATUSES = frozenset({"done", "aborted", "merged", "review", "failed"})


def _resolve_server_label(
    config: OrchestraConfig, snapshot_found: bool, server_running: bool
) -> str:
    if snapshot_found and server_running:
        return "[green]running[/]"
    pid, is_valid = validate_pid_file(config.pid_file)
    if is_valid and pid is not None:
        return "[green]running[/]"
    return "[dim]stopped[/]"


def _compute_effective_server_running(
    snapshot_running: bool, config: OrchestraConfig
) -> bool:
    """Unified server status: snapshot is authoritative, PID-valid is fallback."""
    if snapshot_running:
        return True
    _, pid_valid = validate_pid_file(config.pid_file)
    return pid_valid


def _resolve_repo_name(config_repo: str | None) -> str:
    """Resolve repo name from config or fallback to git remote URL."""
    if config_repo:
        return config_repo
    try:
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
    except (subprocess.SubprocessError, OSError):
        pass
    return "(unknown)"


def _render_runtime_versions() -> None:
    """Render Runtime Versions section showing current versions.

    Displays the current policy and material hashes computed from the
    governance directory contents.
    """
    from vibe3.clients import resolve_runtime_asset
    from vibe3.services.shared import material_loader, policy_loader
    from vibe3.utils import compute_hash_from_loader

    console.print("[bold]Runtime Versions[/] [dim](current)[/]")

    try:
        policies_dir = resolve_runtime_asset(".agent/governance/policies")
        materials_dir = resolve_runtime_asset("supervisor/governance")

        policy_hash = compute_hash_from_loader(policy_loader, policies_dir)
        material_hash = compute_hash_from_loader(material_loader, materials_dir)

        if policy_hash:
            console.print(f"  Policy hash:  {policy_hash}")
        else:
            console.print("  Policy hash:  [dim](no policies found)[/]")

        if material_hash:
            console.print(f"  Material hash: {material_hash}")
        else:
            console.print("  Material hash: [dim](no materials found)[/]")

    except Exception as e:
        console.print(f"  [dim]Error computing versions: {e}[/]")

    console.print()


def _analyze_orchestra_config_sources(config: OrchestraConfig) -> dict[str, str]:
    """Determine the source of each displayed orchestra config value.

    Returns a dict mapping field name to source label:
    - "default" if value matches Pydantic model default
    - "env override" if an env var overrides this field
    - "config override" if a YAML config file overrides the default
    """
    defaults = OrchestraConfig()
    sources: dict[str, str] = {}

    # Check each field
    for field in [
        "max_concurrent_flows",
        "polling_interval",
        "debug_polling_interval",
        "scene_base_ref",
        "repo",
        "manager_usernames",
    ]:
        config_value = getattr(config, field)
        default_value = getattr(defaults, field)

        # Check if env var overrides this field
        config_path = f"orchestra.{field}"
        env_override_found = False

        for rule in OVERRIDE_RULES:
            if rule.config_path == config_path and os.environ.get(rule.env_key):
                sources[field] = "env override"
                env_override_found = True
                break

        if env_override_found:
            continue

        # Check if value differs from default
        if config_value == default_value:
            sources[field] = "default"
        else:
            sources[field] = "config override"

    return sources


def _render_configuration(config: OrchestraConfig) -> None:
    """Render Vibe3 configuration section in status output."""
    sources = _analyze_orchestra_config_sources(config)
    manager = ", ".join(get_manager_usernames(config))
    console.print("[bold]Vibe3 Configuration[/]")

    repo_name = _resolve_repo_name(config.repo)
    console.print(f"  Repo:              {repo_name} ({sources['repo']})")

    console.print(f"  Manager agents:    {manager} ({sources['manager_usernames']})")

    max_concurrent = config.max_concurrent_flows
    console.print(
        f"  Max concurrent:    {max_concurrent} " f"({sources['max_concurrent_flows']})"
    )

    console.print(
        f"  Polling interval:  {config.polling_interval}s "
        f"({sources['polling_interval']})"
    )

    # Add debug mode status
    debug_status = "ON" if config.debug else "OFF"
    debug_interval = config.debug_polling_interval
    console.print(f"    Debug mode:      {debug_status} (when ON: {debug_interval}s)")

    console.print(
        f"  Scene base ref:    {config.scene_base_ref} "
        f"({sources['scene_base_ref']})"
    )
    console.print()

    # Add Configuration Sources section
    console.print("[bold]Configuration Sources:[/]")
    console.print(
        "  Default values from: OrchestraConfig "
        "(src/vibe3/models/orchestra_config.py)"
    )

    # Check global config
    global_config_path = Path.home() / ".vibe" / "settings.yaml"
    global_has_orchestra = False
    if global_config_path.exists():
        try:
            import yaml

            with open(global_config_path) as f:
                global_data = yaml.safe_load(f) or {}
                global_has_orchestra = "orchestra" in global_data
        except Exception:
            pass

    global_status = f"{global_config_path}"
    if not global_has_orchestra:
        global_status += " (no orchestra overrides)"
    console.print(f"  Global config:       {global_status}")

    # Check project config
    project_config_path = Path(".vibe/settings.yaml")
    project_has_orchestra = False
    if project_config_path.exists():
        try:
            import yaml

            with open(project_config_path) as f:
                project_data = yaml.safe_load(f) or {}
                project_has_orchestra = "orchestra" in project_data
        except Exception:
            pass

    project_status = f"{project_config_path}"
    if not project_has_orchestra:
        project_status += " (no orchestra overrides)"
    console.print(f"  Project config:     {project_status}")

    # Check env overrides
    env_overrides = []
    for rule in OVERRIDE_RULES:
        if rule.config_path.startswith("orchestra.") and os.environ.get(rule.env_key):
            env_overrides.append(rule.env_key)

    if env_overrides:
        console.print(f"  Env overrides:      {', '.join(env_overrides)}")
    else:
        console.print("  Env overrides:      none")

    console.print()


def _fetch_system_snapshot(
    config: OrchestraConfig,
) -> tuple["OrchestraSnapshot", bool]:
    """Fetch orchestra snapshot with retry and PID fallback.

    Returns (snapshot, snapshot_found) where snapshot_found is False only
    when the snapshot was generated locally (server not reachable).
    """
    import time
    from dataclasses import replace

    from vibe3.services.orchestra import FlowOrchestratorService, OrchestraStatusService

    snapshot = OrchestraStatusService.fetch_live_snapshot(config)
    if snapshot is None:
        time.sleep(0.5)
        snapshot = OrchestraStatusService.fetch_live_snapshot(config)
    snapshot_found = snapshot is not None

    if not snapshot:
        _, pid_alive = validate_pid_file(config.pid_file)
        if pid_alive:
            time.sleep(0.5)
            snapshot = OrchestraStatusService.fetch_live_snapshot(config)
            snapshot_found = snapshot is not None

    if not snapshot:
        orch_service = OrchestraStatusService(
            config, orchestrator=FlowOrchestratorService(config)
        )
        local_snap = orch_service.snapshot()
        snapshot = replace(local_snap, server_running=False)

    assert snapshot is not None
    return snapshot, snapshot_found


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
    """Render task status dashboard with issue progress panels."""
    validate_trace_options(trace, min_ms)
    if trace:
        enable_method_trace(min_ms=min_ms)

    from vibe3.commands import (
        render_blocked_items,
        render_completed_flows,
        render_epic_items,
        render_human_collab_flows,
        render_issue_progress,
        render_missing_state_items,
        render_pr_ref_items,
        render_remote_items,
        render_rfc_items,
        render_supervisor_issues,
    )
    from vibe3.services.task import (
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

    # Classify issues for rendering
    classified = classify_task_issues_for_rendering(
        data.orchestrated_issues, data.config
    )

    # Render all progress panels
    render_issue_progress(classified["bucketed_items"], data.config)
    console.print()

    render_human_collab_flows(classified["human_collab_items"])
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
    render_epic_items(
        classified["roadmap_epic_items"], classified["open_issue_numbers"]
    )
    render_blocked_items(classified["blocked_items"])

    if all_flows:
        completed_flows = [
            flow
            for flow in data.flows
            if getattr(flow, "flow_status", "active") in COMPLETED_FLOW_STATUSES
        ]
        render_completed_flows(completed_flows)

    # Cross-reference hint for runtime observation layer
    console.print("[dim]For runtime health: vibe3 serve status[/]")


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

    from vibe3.config import load_orchestra_config

    config = load_orchestra_config()
    orch_snapshot, snapshot_found = _fetch_system_snapshot(config)

    if output_format in ("json", "yaml"):
        output_data = {"orchestra": asdict(orch_snapshot)}
        if output_format == "json":
            typer.echo(json.dumps(output_data, indent=2, default=str))
        else:
            import yaml

            typer.echo(
                yaml.dump(output_data, default_flow_style=False, allow_unicode=True)
            )
        return

    _render_system_status(config, orch_snapshot, snapshot_found)
    _render_runtime_versions()
    typer.echo(
        "Use 'vibe3 task status' to view issue progress and ready queue",
        err=True,
    )
