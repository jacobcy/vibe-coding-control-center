"""HeartbeatServer: event loop with service registry and polling fallback."""

import asyncio
import os

from loguru import logger

from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.event_bus import GitHubEvent, ServiceBase


class HeartbeatServer:
    """Manages the orchestra event loop.

    Two event sources:
    - Webhook events (real-time, primary): pushed via emit()
    - Polling tick (fallback): calls service.on_tick() every polling_interval s
    """

    def __init__(self, config: OrchestraConfig) -> None:
        self.config = config
        self._services: list[ServiceBase] = []
        self._event_queue: asyncio.Queue[GitHubEvent] = asyncio.Queue()
        self._semaphore = asyncio.Semaphore(config.max_concurrent_flows)
        self._running = False

    def register(self, service: ServiceBase) -> None:
        """Register a service to receive events and tick callbacks."""
        self._services.append(service)
        logger.bind(domain="orchestra").info(
            f"Registered service: {type(service).__name__}"
        )

    @property
    def service_names(self) -> list[str]:
        return [type(s).__name__ for s in self._services]

    async def emit(self, event: GitHubEvent) -> None:
        """Push a GitHub event onto the queue for async processing."""
        await self._event_queue.put(event)

    async def run(self) -> None:
        """Start heartbeat. Runs until stop() is called."""
        self._running = True
        self._write_pid()
        log = logger.bind(domain="orchestra", action="start")
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
            logger.bind(domain="orchestra", action="tick").debug("Heartbeat tick")
            tasks = [self._tick_service(svc) for svc in self._services]
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _tick_service(self, service: ServiceBase) -> None:
        async with self._semaphore:
            try:
                await service.on_tick()
            except Exception as exc:
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
            asyncio.create_task(self._dispatch_event(event))

    async def _dispatch_event(self, event: GitHubEvent) -> None:
        matching = [
            svc for svc in self._services if event.event_type in svc.event_types
        ]
        if not matching:
            logger.bind(domain="orchestra").debug(
                f"No handler for event_type={event.event_type!r}"
            )
            return
        tasks = [self._handle_with_semaphore(svc, event) for svc in matching]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _handle_with_semaphore(
        self, service: ServiceBase, event: GitHubEvent
    ) -> None:
        async with self._semaphore:
            try:
                await service.handle_event(event)
            except Exception as exc:
                logger.bind(domain="orchestra").error(
                    f"Event error in {type(service).__name__}: {exc}"
                )

    # -- pid management --

    def _write_pid(self) -> None:
        pid_file = self.config.pid_file
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text(str(os.getpid()))

    def _cleanup(self) -> None:
        if self.config.pid_file.exists():
            self.config.pid_file.unlink(missing_ok=True)
