"""GitHub label poller."""

import json
import subprocess
import time

from loguru import logger

from vibe3.models.orchestration import IssueState
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.dispatcher import Dispatcher
from vibe3.orchestra.models import IssueInfo
from vibe3.orchestra.router import Router


class Poller:
    """Polls GitHub for label changes and triggers commands."""

    def __init__(self, config: OrchestraConfig):
        self.config = config
        self.router = Router()
        self.dispatcher = Dispatcher(dry_run=config.dry_run)
        self._state_cache: dict[int, IssueState | None] = {}
        self._running = False

    def start(self) -> None:
        """Start the polling loop."""
        self._running = True
        self._write_pid()

        log = logger.bind(domain="orchestra", action="start")
        log.info(
            f"Starting Orchestra daemon (interval: {self.config.polling_interval}s)"
        )

        try:
            while self._running:
                self.tick()
                time.sleep(self.config.polling_interval)
        except KeyboardInterrupt:
            log.info("Shutting down Orchestra daemon")
        finally:
            self._cleanup()

    def stop(self) -> None:
        """Stop the polling loop."""
        self._running = False

    def tick(self) -> None:
        """Single polling iteration."""
        log = logger.bind(domain="orchestra", action="tick")

        try:
            issues = self.fetch_issues()
            log.debug(f"Found {len(issues)} issues with state labels")

            for issue in issues:
                previous_state = self._state_cache.get(issue.number)
                trigger = self.router.route(issue, previous_state)

                if trigger:
                    prev = previous_state.value if previous_state else "none"
                    curr = issue.state.value if issue.state else "none"
                    log.info(f"State change: #{issue.number} {prev} -> {curr}")
                    self.dispatcher.dispatch(trigger)

                self._state_cache[issue.number] = issue.state

        except Exception as e:
            log.error(f"Tick failed: {e}")

    def fetch_issues(self) -> list[IssueInfo]:
        """Fetch issues with state labels from GitHub."""
        cmd = [
            "gh",
            "issue",
            "list",
            "--state",
            "open",
            "--json",
            "number,title,labels,url",
            "--limit",
            "100",
        ]

        if self.config.repo:
            cmd.extend(["--repo", self.config.repo])

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Failed to fetch issues: {result.stderr}")
            return []

        data = json.loads(result.stdout)
        issues = []

        for item in data:
            labels = [label["name"] for label in item.get("labels", [])]
            state = None

            for label in labels:
                state = IssueState.from_label(label)
                if state:
                    break

            issues.append(
                IssueInfo(
                    number=item["number"],
                    title=item["title"],
                    state=state,
                    labels=labels,
                    url=item.get("url"),
                )
            )

        return issues

    def _write_pid(self) -> None:
        """Write PID file."""
        import os

        pid_file = self.config.pid_file
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text(str(os.getpid()))

    def _cleanup(self) -> None:
        """Clean up on shutdown."""
        if self.config.pid_file.exists():
            self.config.pid_file.unlink()
