"""HeartbeatServer: event loop with service registry and polling fallback."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol

from loguru import logger

from vibe3.models import OrchestraConfig
from vibe3.observability import append_orchestra_event, append_orchestra_run_separator

from .periodic_check_executor import execute_periodic_check
from .service_protocol import ServiceBase

if TYPE_CHECKING:
    from vibe3.domain.failed_gate import GateResult


class FailedGateProtocol(Protocol):
    """Protocol for FailedGate to avoid circular dependency.

    This protocol defines the interface used by HeartbeatServer,
    allowing runtime layer to avoid importing from domain layer.
    """

    def check(self) -> GateResult:
        """Check if orchestra dispatch should be frozen.

        Returns:
            GateResult with blocked status and reason
        """
        ...

    def increment_blocked_ticks(self) -> None:
        """Increment blocked_ticks counter.

        Called each tick when gate is ACTIVE.
        """
        ...


PACK_REFS_INTERVAL_TICKS = 100


class HeartbeatServer:
    """Manages the orchestra event loop.

    Two event sources:
    - Webhook events (real-time, primary): pushed via emit()
    - Polling tick (fallback): calls service.on_tick() every polling_interval s
    """

    def __init__(
        self,
        config: OrchestraConfig,
        failed_gate: FailedGateProtocol | None = None,
    ) -> None:
        self.config = config
        self._failed_gate = failed_gate
        self._services: list[ServiceBase] = []
        self._semaphore = asyncio.Semaphore(config.max_concurrent_flows)
        self._running = False
        self._tick_count = 0
        self._shutdown_callback: Callable[[], object] | None = None

    def register(self, service: ServiceBase) -> None:
        """Register a service to receive events and tick callbacks."""
        self._services.append(service)
        append_orchestra_event(
            "server",
            f"registered service: {service.service_name}",
        )
        logger.bind(domain="orchestra").info(
            f"Registered service: {service.service_name}"
        )

    def set_shutdown_callback(self, callback: Callable[[], object]) -> None:
        """Register a callback to run when the server stops.

        Called exactly once during _cleanup(), after the event loop exits.
        Used by the server assembly to hook in session lifecycle cleanup
        (e.g. SessionRegistryService.clear_all_sessions).
        """
        self._shutdown_callback = callback

    @property
    def service_names(self) -> list[str]:
        return [s.service_name for s in self._services]

    @property
    def running(self) -> bool:
        """Whether the heartbeat server is currently running."""
        return self._running

    async def run(self) -> None:
        """Start heartbeat. Runs until stop() is called."""
        self._running = True
        # PID file is written by serve start command (app.py) before launching server
        log = logger.bind(domain="orchestra", action="start")
        append_orchestra_run_separator()
        append_orchestra_event(
            "server",
            (
                f"start tick_interval={self.config.polling_interval}s "
                f"polling_enabled={self.config.polling.enabled} "
                f"max_concurrent={self.config.max_concurrent_flows} "
                f"services={','.join(self.service_names)}"
            ),
        )
        dispatch_services = [
            service.service_name
            for service in self._services
            if service.is_dispatch_service
        ]
        observer_services = [
            service.service_name
            for service in self._services
            if not service.is_dispatch_service
        ]
        append_orchestra_event(
            "server",
            "dispatchers: "
            + (", ".join(dispatch_services) if dispatch_services else "(none)"),
        )
        append_orchestra_event(
            "server",
            "observers: "
            + (", ".join(observer_services) if observer_services else "(none)"),
        )
        log.info(
            f"HeartbeatServer started (tick_interval={self.config.polling_interval}s, "
            f"polling_enabled={self.config.polling.enabled}, "
            f"max_concurrent={self.config.max_concurrent_flows}, "
            f"services={self.service_names})"
        )
        try:
            async with asyncio.TaskGroup() as tg:
                if self.config.polling.enabled:
                    tg.create_task(self._tick_loop())
                else:
                    # Keep server running even when polling is disabled
                    # (for HTTP-only mode: /status, /mcp endpoints)
                    tg.create_task(self._idle_loop())
        except* Exception as eg:
            for exc in eg.exceptions:
                append_orchestra_event("server", f"error: {exc}")
                log.error(f"HeartbeatServer error: {exc}")
        finally:
            self._cleanup()

    def stop(self) -> None:
        """Signal the server to stop."""
        self._running = False

    # -- internal loops --

    async def _tick_loop(self) -> None:
        """Periodic tick: calls on_tick() for every registered service."""
        while self._running:
            await asyncio.sleep(self.config.polling_interval)
            if not self._running:
                break

            self._tick_count += 1
            tick_number = self._tick_count
            started_at = time.perf_counter()
            logger.bind(domain="orchestra", action="tick").debug("Heartbeat tick")

            # Write tick marker for readability (INFO level - shows timeline)
            # Blank line before each tick for visual separation
            append_orchestra_event("server", "")
            append_orchestra_event("server", f"tick #{tick_number} start")

            # Check FailedGate before dispatching
            if self._failed_gate is not None:
                gate_result = self._failed_gate.check()

                if gate_result.blocked:
                    # Gate is ACTIVE - skip dispatch and increment blocked_ticks
                    self._failed_gate.increment_blocked_ticks()
                    append_orchestra_event(
                        "server",
                        (
                            f"tick #{tick_number} blocked by failed gate: "
                            f"{gate_result.reason}"
                        ),
                    )
                    logger.bind(domain="orchestra", action="tick").warning(
                        f"Tick #{tick_number} blocked by failed gate: "
                        f"{gate_result.reason}"
                    )
                    # Skip service dispatch, continue to next tick
                    continue

            # Cleanup old error records (maintenance)
            # Delay import to avoid circular dependency
            from vibe3.services import ErrorTrackingService

            error_tracking = ErrorTrackingService.get_instance()

            # Cleanup retention-based errors
            try:
                deleted_old = error_tracking.cleanup_old_errors()
            except Exception as exc:
                append_orchestra_event(
                    "server",
                    f"tick #{tick_number} cleanup_old_errors failed: {exc}",
                    level="WARNING",
                )
                logger.bind(domain="orchestra", action="cleanup").warning(
                    f"cleanup_old_errors failed: {exc}"
                )
            else:
                if deleted_old > 0:
                    append_orchestra_event(
                        "server",
                        (
                            f"tick #{tick_number} cleanup: deleted {deleted_old} "
                            "old error records"
                        ),
                        level="DEBUG",
                    )
                    logger.bind(domain="orchestra", action="cleanup").debug(
                        f"Cleaned up {deleted_old} old error records "
                        f"(retention={error_tracking.retention_days}d)"
                    )

            # Periodic Git ref packing to prevent stale references
            if tick_number % PACK_REFS_INTERVAL_TICKS == 0:
                try:
                    from vibe3.clients import GitClient

                    GitClient().pack_refs_all()
                    append_orchestra_event(
                        "server",
                        f"tick #{tick_number} pack-refs completed",
                    )
                except Exception as exc:
                    append_orchestra_event(
                        "server",
                        f"tick #{tick_number} pack-refs failed: {exc}",
                        level="WARNING",
                    )
                    logger.bind(domain="orchestra", action="maintenance").warning(
                        f"pack-refs failed: {exc}"
                    )

            # Periodic consistency check
            # (PR merged/closed, issue closed, label anomalies, etc.)
            if (
                self.config.periodic_check.enabled
                and tick_number % self.config.periodic_check.interval_ticks == 0
            ):
                try:
                    await self._run_periodic_check(tick_number)
                except Exception as exc:
                    append_orchestra_event(
                        "server",
                        f"tick #{tick_number} periodic check failed: {exc}",
                        level="WARNING",
                    )
                    logger.bind(domain="orchestra", action="periodic_check").warning(
                        f"Periodic check failed: {exc}"
                    )

            tasks = []
            tick_services: list[str] = []
            for svc in self._services:
                tick_services.append(svc.service_name)
                tasks.append(self._tick_service(svc, tick_number))

            # Only log services list in DEBUG mode
            if tick_services:
                append_orchestra_event(
                    "server",
                    "tick #"
                    + str(tick_number)
                    + " services: "
                    + ", ".join(tick_services),
                    level="DEBUG",
                )
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

            duration = time.perf_counter() - started_at
            append_orchestra_event(
                "server",
                f"tick #{tick_number} completed in {duration:.2f}s",
            )

            if self.config.debug and tick_number >= self.config.debug_max_ticks:
                append_orchestra_event(
                    "server",
                    (
                        "debug tick limit reached "
                        f"({self.config.debug_max_ticks}), stopping server"
                    ),
                )
                self.stop()

    async def _tick_service(self, service: ServiceBase, tick_id: int) -> None:
        async with self._semaphore:
            try:
                await service.on_tick(tick_id)
            except Exception as exc:
                append_orchestra_event(
                    "server",
                    f"tick error in {type(service).__name__}: {exc}",
                )
                logger.bind(domain="orchestra").warning(
                    f"Tick error in {type(service).__name__}: {exc}"
                )

    async def _run_periodic_check(self, tick_number: int) -> None:
        """Run periodic consistency check (every N ticks)."""
        # Delay imports to avoid circular dependencies
        from vibe3.clients import SQLiteClient
        from vibe3.services import CheckService

        store = SQLiteClient()
        check_service = CheckService(store=store)

        await execute_periodic_check(
            self.config.periodic_check,
            tick_number,
            check_service,
        )

    async def _idle_loop(self) -> None:
        """Keep server running when polling is disabled (HTTP-only mode)."""
        while self._running:
            await asyncio.sleep(1)

    def _cleanup(self) -> None:
        if self._shutdown_callback is not None:
            try:
                self._shutdown_callback()
            except Exception as exc:
                logger.bind(domain="orchestra").warning(
                    f"shutdown callback raised: {exc}"
                )
        append_orchestra_event("server", "stop")
        if self.config.pid_file.exists():
            self.config.pid_file.unlink(missing_ok=True)
