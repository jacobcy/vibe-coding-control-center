"""Service for displaying Orchestra server status."""

from __future__ import annotations

import re

from rich.console import Console
from rich.table import Table

from vibe3.config import load_orchestra_config
from vibe3.models import OrchestraConfig
from vibe3.observability import orchestra_events_log_path
from vibe3.services.orchestra.error_tracking.service import ErrorTrackingService
from vibe3.utils import (
    CODEAGENT_WRAPPER_RE,
    clean_error_message,
    format_age_aware_time,
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
