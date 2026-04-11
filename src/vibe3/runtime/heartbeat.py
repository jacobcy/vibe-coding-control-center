"""HeartbeatServer: event loop with service registry and polling fallback."""

from __future__ import annotations

import asyncio
import os
import time
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.orchestra.failed_gate import GateResult
from vibe3.orchestra.logging import (
    append_orchestra_event,
    append_orchestra_run_separator,
)
from vibe3.runtime.service_protocol import GitHubEvent, ServiceBase

if TYPE_CHECKING:
    from vibe3.orchestra.failed_gate import FailedGate


class HeartbeatServer:
    """Manages the orchestra event loop.

    Two event sources:
    - Webhook events (real-time, primary): pushed via emit()
    - Polling tick (fallback): calls service.on_tick() every polling_interval s
    """

    def __init__(
        self,
        config: OrchestraConfig,
        failed_gate: FailedGate | None = None,
    ) -> None:
        self.config = config
        self._failed_gate = failed_gate
        self._services: list[ServiceBase] = []
        self._event_queue: asyncio.Queue[GitHubEvent] = asyncio.Queue()
        self._semaphore = asyncio.Semaphore(config.max_concurrent_flows)
        self._running = False
        self._pending_tasks: set[asyncio.Task[None]] = set()
        self._tick_count = 0

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

    @property
    def service_names(self) -> list[str]:
        return [s.service_name for s in self._services]

    @property
    def queue_size(self) -> int:
        """Current number of events waiting in the queue."""
        return self._event_queue.qsize()

    @property
    def running(self) -> bool:
        """Whether the heartbeat server is currently running."""
        return self._running

    async def emit(self, event: GitHubEvent) -> None:
        """Push a GitHub event onto the queue for async processing."""
        await self._event_queue.put(event)

    async def run(self) -> None:
        """Start heartbeat. Runs until stop() is called."""
        self._running = True
        self._write_pid()
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
                tg.create_task(self._event_loop())
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

            # Failed gate check for dispatchers
            gate_result = GateResult.open()
            if self._failed_gate:
                gate_result = self._failed_gate.check()

            self._tick_count += 1
            tick_number = self._tick_count
            started_at = time.perf_counter()
            logger.bind(domain="orchestra", action="tick").debug("Heartbeat tick")

            # Write tick marker for readability (INFO level - shows timeline)
            append_orchestra_event("server", f"tick #{tick_number} start")
            if gate_result.blocked:
                append_orchestra_event(
                    "server",
                    (
                        f"heartbeat tick #{tick_number} frozen by state/failed issue "
                        f"#{gate_result.issue_number or '?'}"
                        + (
                            f" reason={gate_result.reason}"
                            if gate_result.reason
                            else ""
                        )
                    ),
                )

            tasks = []
            tick_services: list[str] = []
            blocked_services: list[str] = []
            for svc in self._services:
                if gate_result.blocked and svc.is_dispatch_service:
                    blocked_services.append(svc.service_name)
                    logger.bind(
                        domain="orchestra",
                        action="tick_blocked",
                        service=type(svc).__name__,
                    ).debug("Skip tick: dispatch blocked")
                    continue
                tick_services.append(svc.service_name)
                tasks.append(self._tick_service(svc))

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
            if blocked_services:
                append_orchestra_event(
                    "server",
                    "tick #"
                    + str(tick_number)
                    + " blocked dispatchers: "
                    + ", ".join(blocked_services),
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

    async def _tick_service(self, service: ServiceBase) -> None:
        async with self._semaphore:
            try:
                await service.on_tick()
            except Exception as exc:
                append_orchestra_event(
                    "server",
                    f"tick error in {type(service).__name__}: {exc}",
                )
                logger.bind(domain="orchestra").error(
                    f"Tick error in {type(service).__name__}: {exc}"
                )

    async def _event_loop(self) -> None:
        """Drain the event queue and dispatch to matching services."""
        while self._running:
            try:
                event = await asyncio.wait_for(self._event_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            task = asyncio.create_task(self._dispatch_event(event))
            self._pending_tasks.add(task)
            task.add_done_callback(self._pending_tasks.discard)

    async def _dispatch_event(self, event: GitHubEvent) -> None:
        # Check for failed gate to determine if we block dispatch services
        gate_result = GateResult.open()
        if self._failed_gate:
            gate_result = self._failed_gate.check()

        matching = [
            svc for svc in self._services if event.event_type in svc.event_types
        ]

        if not matching:
            append_orchestra_event(
                "server",
                f"no handler for event_type={event.event_type}",
            )
            logger.bind(domain="orchestra").debug(
                f"No handler for event_type={event.event_type!r}"
            )
            return

        tasks = []
        for svc in matching:
            if gate_result.blocked and svc.is_dispatch_service:
                logger.bind(
                    domain="orchestra",
                    action="event_blocked",
                    service=type(svc).__name__,
                ).warning(
                    f"Event {event.event_type} dispatch frozen for "
                    f"{type(svc).__name__} by failed issue #{gate_result.issue_number}"
                )
                append_orchestra_event(
                    "server",
                    f"event {event.event_type} blocked for "
                    f"{type(svc).__name__} by state/failed issue "
                    f"#{gate_result.issue_number or '?'}",
                )
                continue
            tasks.append(self._handle_with_semaphore(svc, event))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _handle_with_semaphore(
        self, service: ServiceBase, event: GitHubEvent
    ) -> None:
        async with self._semaphore:
            try:
                await service.handle_event(event)
            except Exception as exc:
                append_orchestra_event(
                    "server",
                    f"event error in {type(service).__name__}: {exc}",
                )
                logger.bind(domain="orchestra").error(
                    f"Event error in {type(service).__name__}: {exc}"
                )

    # -- pid management --

    def _write_pid(self) -> None:
        pid_file = self.config.pid_file
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text(str(os.getpid()))

    def _cleanup(self) -> None:
        append_orchestra_event("server", "stop")
        if self.config.pid_file.exists():
            self.config.pid_file.unlink(missing_ok=True)
