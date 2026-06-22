"""Service for displaying Orchestra server status."""

from __future__ import annotations

import re
from typing import Any

from rich.console import Console
from rich.table import Table

from vibe3.clients import SQLiteClient
from vibe3.config import load_orchestra_config
from vibe3.models import OrchestraConfig
from vibe3.observability import orchestra_events_log_path
from vibe3.services.orchestra.error_tracking.service import ErrorTrackingService
from vibe3.utils import (
    CODEAGENT_WRAPPER_RE,
    clean_error_message,
    format_age_aware_time,
    job_to_dict,
    orchestra_tmux_session_exists,
    validate_pid_file,
)


class ServeStatusService:
    """Service for displaying Orchestra server status and diagnostics."""

    def __init__(self, config: OrchestraConfig | None = None) -> None:
        """Initialize status service.

        Args:
            config: Orchestra config (loads default if None)
        """
        self.config = config or load_orchestra_config()
        self.console = Console()

    def display_status(
        self,
        pid: int | None,
        is_valid: bool,
        tmux_exists: bool,
    ) -> None:
        """Display complete server status.

        Args:
            pid: Process ID from PID file
            is_valid: Whether PID is valid
            tmux_exists: Whether tmux session exists
        """
        self._display_daemon_status(pid, is_valid, tmux_exists)
        self._display_log_path()
        self._display_config()
        self._display_recent_activity()
        self._display_runtime_jobs()
        self._display_failed_gate()
        self._display_error_tracking()

    @staticmethod
    def _clean_error_message(error_message: str, max_length: int = 100) -> str:
        """Clean error message by removing TMPDIR and other noise.

        Args:
            error_message: Raw error message from error_log
            max_length: Maximum length to truncate (default 100)

        Returns:
            Cleaned and truncated error message
        """
        # Remove codeagent-wrapper prefix, then delegate shared cleaning
        cleaned = CODEAGENT_WRAPPER_RE.sub("", error_message)
        cleaned = clean_error_message(cleaned)

        # Truncate to max_length
        return cleaned[:max_length] if len(cleaned) > max_length else cleaned

    def _display_daemon_status(
        self,
        pid: int | None,
        is_valid: bool,
        tmux_exists: bool,
    ) -> None:
        """Display daemon running status."""
        if pid is None:
            if tmux_exists:
                self.console.print(
                    "[yellow]Orchestra server running in tmux "
                    "session (PID file missing)[/yellow]"
                )
            else:
                self.console.print("[red]Orchestra server is not running[/red]")
        elif not is_valid:
            if tmux_exists:
                self.console.print(
                    "[yellow]Orchestra server running in tmux session "
                    f"(stale PID file points to non-orchestra process {pid})[/yellow]"
                )
            else:
                self.console.print(
                    f"[red]Orchestra server is not running "
                    f"(stale PID file, process {pid} is not orchestra)[/red]"
                )
        else:
            self.console.print(f"[green]Orchestra server running (PID: {pid})[/green]")

    def _display_log_path(self) -> None:
        """Display the orchestra events log path."""
        log_path = orchestra_events_log_path()
        self.console.print(f"Log: {log_path}")

    def _display_config(self) -> None:
        """Display configuration summary."""
        from vibe3.services.orchestra.status import OrchestraStatusService

        # Try to get runtime values from live server
        polling_interval = self.config.polling_interval
        live = OrchestraStatusService.fetch_live_snapshot(self.config)
        if live is not None:
            polling_interval = live.polling_interval

        if polling_interval != self.config.polling_interval:
            self.console.print(
                f"  - Tick interval: {polling_interval}s "
                f"[dim](override, config: {self.config.polling_interval}s)[/dim]"
            )
        else:
            self.console.print(f"  - Tick interval: {polling_interval}s")
        self.console.print(f"  - Max concurrent: {self.config.max_concurrent_flows}\n")

    def _display_recent_activity(self) -> None:
        """Display recent tick activity from events.log."""
        events_log = orchestra_events_log_path()
        if not events_log.exists():
            return

        try:
            log_content = events_log.read_text()

            # Extract last tick info
            tick_matches = re.findall(
                r"\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\] "
                r"\[server\] tick #(\d+) (start|completed)",
                log_content,
            )
            if not tick_matches:
                return

            last_tick = tick_matches[-1]
            tick_time, tick_num, tick_status = last_tick
            status_str = "in progress" if tick_status == "start" else "completed"
            self.console.print(
                "[bold]Orchestration Activity[/] [dim](runtime, not flow timeline)[/]"
            )
            self.console.print(f"  - Tick #{tick_num} ({status_str} at {tick_time})")

            # Extract dispatcher activity for this tick
            dispatcher_matches = re.findall(
                rf"\[{tick_time[:10]}.*?\] \[dispatcher\] "
                r"GlobalDispatchCoordinator: (.+)",
                log_content,
            )
            if dispatcher_matches:
                self.console.print("  - Dispatcher activity:")
                for match in dispatcher_matches[-5:]:  # Show last 5 events
                    # Remove ANSI color codes for display
                    clean_match = re.sub(r"\x1b\[[0-9;]*m", "", match)
                    self.console.print(f"    • {clean_match}")
                self.console.print()

        except Exception as exc:
            self.console.print(
                f"[yellow]Warning: Could not parse events.log: {exc}[/yellow]\n"
            )

    def _display_failed_gate(self) -> None:
        """Display FailedGate status."""
        # Dynamic import to avoid static analysis detecting circular dependency
        import importlib

        failed_gate_module = importlib.import_module("vibe3.domain.failed_gate")
        FailedGate = failed_gate_module.FailedGate  # noqa: N806

        failed_gate = FailedGate()
        gate_status = failed_gate.get_status()

        self.console.print("[bold]FailedGate Status:[/bold]")
        if gate_status.is_active:
            self.console.print("[red]  State: ACTIVE (blocking dispatch)[/red]")
            self.console.print(f"  Reason: {gate_status.reason}")
            if gate_status.triggered_at:
                self.console.print(f"  Triggered at: {gate_status.triggered_at}")
            if gate_status.triggered_by_error_code:
                self.console.print(
                    f"  Error code: {gate_status.triggered_by_error_code}"
                )
            self.console.print(f"  Blocked ticks: {gate_status.blocked_ticks}")
            self.console.print(
                '\n[yellow]To resume:[/yellow] vibe3 serve resume --reason "<reason>"'
            )
        else:
            self.console.print("[green]  State: OPEN (normal operation)[/green]")
        self.console.print()

    def _display_runtime_jobs(self) -> None:
        """Display launched role sessions from durable runtime_session state."""
        import importlib

        module = importlib.import_module("vibe3.execution.job_monitor_service")
        job_svc = module.JobMonitorService(store=SQLiteClient())
        snapshot = job_svc.snapshot()

        self.console.print(
            "[bold]Runtime Jobs[/] "
            "[dim](launched role sessions; dispatcher decisions are above)[/]"
        )

        if not snapshot.active_jobs and not snapshot.recent_jobs:
            self.console.print("  No runtime jobs recorded")
            self.console.print()
            return

        if snapshot.active_jobs:
            table = Table(title="Running / Queued", show_lines=True)
            table.add_column("Role", style="magenta", width=8)
            table.add_column("Status", style="green", width=8)
            table.add_column("Target", style="yellow")
            table.add_column("Started", style="dim", width=12)
            table.add_column("Log", style="dim")

            for job in snapshot.active_jobs:
                table.add_row(
                    _job_role_display(job),
                    _job_status_display(job).upper(),
                    _job_target_display(job),
                    format_age_aware_time(job.started_at) if job.started_at else "-",
                    _job_log_display(job),
                )
            self.console.print(table)

        if snapshot.recent_jobs:
            table = Table(title="Recent Sessions", show_lines=True)
            table.add_column("Role", style="magenta", width=8)
            table.add_column("Status", style="yellow", width=9)
            table.add_column("Target", style="yellow")
            table.add_column("Ended", style="dim", width=12)
            table.add_column("Log", style="dim")

            for job in snapshot.recent_jobs:
                table.add_row(
                    _job_role_display(job),
                    _job_status_display(job).upper(),
                    _job_target_display(job),
                    (
                        format_age_aware_time(job.completed_at)
                        if job.completed_at
                        else "-"
                    ),
                    _job_log_display(job),
                )
            self.console.print(table)

        self.console.print(
            f"  Summary: {snapshot.running_count} running, "
            f"{snapshot.completed_count} completed, "
            f"{snapshot.failed_count} failed"
        )
        self.console.print()

    def _display_error_tracking(self) -> None:
        """Display error tracking status with severity breakdown."""
        error_tracking = ErrorTrackingService.get_instance()
        # Get ALL errors in database (not just windowed)
        all_errors_status = error_tracking.get_all_errors_status()
        # Also get windowed status for threshold monitoring
        windowed_status = error_tracking.get_status()

        self.console.print("[bold]Error Tracking:[/bold]")
        if all_errors_status["total_errors"] > 0:
            # Show severity-based counts for all errors
            self.console.print(f"  Total errors: {all_errors_status['total_errors']}")
            self.console.print(f"  - CRITICAL: {all_errors_status['critical_count']}")
            self.console.print(f"  - ERROR: {all_errors_status['error_count']}")
            self.console.print(f"  - WARNING: {all_errors_status['warning_count']}")

            # Show windowed context if there are recent errors
            if windowed_status["total_errors"] > 0:
                self.console.print(
                    f"\n  [dim]Windowed ({windowed_status['time_window_minutes']}min): "
                    f"{windowed_status['total_errors']} errors "
                    f"(threshold: {windowed_status['threshold']})[/dim]"
                )

            # Show recent errors
            recent_errors = error_tracking.get_recent_errors(limit=10)
            if recent_errors:
                table = Table(title="\n  Recent Errors (last 10)", show_lines=True)
                table.add_column("Tick", style="cyan", width=6)
                table.add_column("Issue", style="yellow", width=10)
                table.add_column("Severity", style="red", width=8)
                table.add_column("Code", style="magenta")
                table.add_column("Time", style="dim", width=19)
                table.add_column("Message", style="white")

                for err in recent_errors:
                    # Format time with age-aware display (convert UTC to local timezone)
                    time_str = err.get("created_at", "")
                    time_display = format_age_aware_time(time_str)

                    # Format issue number (NULL for governance errors)
                    issue_num = err.get("issue_number")
                    if issue_num is None:
                        issue_display = "governance"
                    else:
                        issue_display = f"#{issue_num}"

                    # Get severity from error record
                    severity = err.get("severity", "ERROR")
                    severity_display = severity if severity else "ERROR"

                    table.add_row(
                        str(err["tick_id"]),
                        issue_display,
                        severity_display,
                        err["error_code"],
                        time_display,
                        self._clean_error_message(err["error_message"]),
                    )

                self.console.print(table)
        else:
            self.console.print("  No errors recorded")


def fetch_serve_status_data(config: OrchestraConfig) -> dict[str, Any]:
    """Fetch serve status data as JSON-serializable dict for API endpoint.

    Args:
        config: Orchestra configuration.

    Returns:
        Dict with daemon status, heartbeat, dispatch activity, FailedGate,
        error tracking, and job monitoring data.
    """
    import importlib

    execution_module = importlib.import_module("vibe3.execution")
    job_monitor_service = execution_module.JobMonitorService

    # Daemon status (uses utils functions, no layer violation)
    instance_info, is_running = validate_pid_file(config.pid_file)
    pid = instance_info.pid if instance_info else None
    tmux_exists = orchestra_tmux_session_exists()

    daemon_status = {
        "pid": pid,
        "is_valid": is_running,
        "tmux_exists": tmux_exists,
        "port": config.port,
        "log_path": str(orchestra_events_log_path()),
    }

    # Heartbeat ticks from events.log
    heartbeat = {
        "tick_count": 0,
        "last_tick_time": None,
        "polling_interval": config.polling_interval,
    }

    events_log = orchestra_events_log_path()
    if events_log.exists():
        try:
            log_content = events_log.read_text()
            tick_matches = re.findall(
                r"\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\] "
                r"\[server\] tick #(\d+) (start|completed)",
                log_content,
            )
            if tick_matches:
                last_tick = tick_matches[-1]
                tick_time, tick_num, _tick_status = last_tick
                heartbeat["tick_count"] = int(tick_num)
                heartbeat["last_tick_time"] = tick_time
        except Exception:
            pass

    # Try to get runtime polling interval from live snapshot
    from vibe3.services.orchestra.status import OrchestraStatusService

    live = OrchestraStatusService.fetch_live_snapshot(config)
    if live is not None:
        heartbeat["polling_interval"] = live.polling_interval

    # Dispatch activity from events.log (last 5 events)
    dispatch_activity = []
    if events_log.exists():
        try:
            log_content = events_log.read_text()
            tick_matches = re.findall(
                r"\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\] "
                r"\[server\] tick #(\d+) (start|completed)",
                log_content,
            )
            if tick_matches:
                last_tick_time = tick_matches[-1][0]
                dispatcher_matches = re.findall(
                    rf"\[{last_tick_time[:10]}.*?\] \[dispatcher\] "
                    r"GlobalDispatchCoordinator: (.+)",
                    log_content,
                )
                for match in dispatcher_matches[-5:]:
                    clean_match = re.sub(r"\x1b\[[0-9;]*m", "", match)
                    # Truncate long entries to avoid confusing display in HTML
                    if len(clean_match) > 200:
                        clean_match = clean_match[:197] + "..."
                    dispatch_activity.append(clean_match)
        except Exception:
            pass

    # FailedGate status
    failed_gate_module = importlib.import_module("vibe3.domain.failed_gate")
    FailedGate = failed_gate_module.FailedGate  # noqa: N806
    failed_gate = FailedGate()
    gate_status = failed_gate.get_status()

    failed_gate_data = {
        "is_active": gate_status.is_active,
        "reason": gate_status.reason,
        "triggered_at": gate_status.triggered_at,
        "triggered_by_error_code": gate_status.triggered_by_error_code,
        "cleared_at": gate_status.cleared_at,
        "cleared_by": gate_status.cleared_by,
        "cleared_reason": gate_status.cleared_reason,
        "blocked_ticks": gate_status.blocked_ticks,
    }

    # Error tracking
    error_tracking_svc = ErrorTrackingService.get_instance()
    all_errors_status = error_tracking_svc.get_all_errors_status()
    windowed_status = error_tracking_svc.get_status()
    recent_errors = error_tracking_svc.get_recent_errors(limit=10)

    error_tracking = {
        "total_errors": all_errors_status["total_errors"],
        "critical_count": all_errors_status["critical_count"],
        "error_count": all_errors_status["error_count"],
        "warning_count": all_errors_status["warning_count"],
        "windowed": {
            "total_errors": windowed_status["total_errors"],
            "time_window_minutes": windowed_status["time_window_minutes"],
            "threshold": windowed_status["threshold"],
        },
        "recent_errors": [
            {
                "tick_id": err["tick_id"],
                "issue_number": err.get("issue_number"),
                "severity": err.get("severity", "ERROR"),
                "error_code": err["error_code"],
                "created_at": err.get("created_at", ""),
                "error_message": ServeStatusService._clean_error_message(
                    err["error_message"]
                ),
            }
            for err in recent_errors
        ],
    }

    # Job monitoring
    if getattr(job_monitor_service, "__module__", "") == (
        "vibe3.execution.job_monitor_service"
    ):
        job_svc = job_monitor_service(store=SQLiteClient())
    else:
        job_svc = job_monitor_service()
    jobs_snapshot = job_svc.snapshot()

    jobs = {
        "active": [job_to_dict(job) for job in jobs_snapshot.active_jobs],
        "recent": [job_to_dict(job) for job in jobs_snapshot.recent_jobs],
        "summary": {
            "running": jobs_snapshot.running_count,
            "completed": jobs_snapshot.completed_count,
            "failed": jobs_snapshot.failed_count,
        },
    }

    return {
        "daemon": daemon_status,
        "heartbeat": heartbeat,
        "dispatch_activity": dispatch_activity,
        "failed_gate": failed_gate_data,
        "error_tracking": error_tracking,
        "jobs": jobs,
    }


def _job_status_display(job: Any) -> str:
    """Return the most specific status available for a job row."""
    return str(job.runtime_status or job.status.value)


def _job_target_display(job: Any) -> str:
    """Return compact target label for a job row."""
    if job.issue_number > 0:
        return f"#{job.issue_number}"
    return str(job.branch or "-")


def _job_role_display(job: Any) -> str:
    """Return role label, preserving runtime role when encoded in session name."""
    parts = str(job.actor_id).split("-")
    if len(parts) >= 2 and parts[0] == "vibe3":
        return parts[1]
    return str(job.job_type.value)


def _job_log_display(job: Any) -> str:
    """Return compact log path for a runtime job."""
    log_path = getattr(job, "log_path", None)
    if not log_path:
        return "-"
    parts = str(log_path).split("/")
    if len(parts) >= 2:
        return "/".join(parts[-2:])
    return str(log_path)
