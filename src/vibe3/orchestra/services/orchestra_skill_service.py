"""OrchestraSkillService: periodically trigger vibe-orchestra skill."""

from __future__ import annotations

import asyncio
import time

from loguru import logger

from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.dispatcher import Dispatcher
from vibe3.orchestra.event_bus import GitHubEvent, ServiceBase


class OrchestraSkillService(ServiceBase):
    """Periodically trigger vibe-orchestra skill for issue triage."""

    event_types: list[str] = []

    def __init__(
        self,
        config: OrchestraConfig,
        dispatcher: Dispatcher | None = None,
    ) -> None:
        self.config = config
        self._dispatcher = dispatcher or Dispatcher(config, dry_run=config.dry_run)
        self._last_trigger: float = 0.0
        self._running: bool = False

    async def handle_event(self, event: GitHubEvent) -> None:
        pass

    async def on_tick(self) -> None:
        if self._running:
            return

        elapsed = time.time() - self._last_trigger
        if elapsed < self.config.polling_interval:
            return

        self._running = True
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._dispatch_skill)
        finally:
            self._running = False
            self._last_trigger = time.time()

    def _dispatch_skill(self) -> None:
        skill_name = self.config.orchestra_skill.skill_name
        log = logger.bind(domain="orchestra", action="skill_trigger", skill=skill_name)

        log.info(f"Triggering orchestra skill: {skill_name}")

        if self.config.dry_run:
            log.info("Dry run mode enabled")
            return

        self._dispatcher.dispatch_skill(skill_name)
