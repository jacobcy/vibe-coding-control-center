"""GitHub label poller with async dispatch."""

import asyncio
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor

from loguru import logger

from vibe3.models.orchestration import IssueState
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.dispatcher import Dispatcher
from vibe3.orchestra.master_handler import MasterAgentHandler
from vibe3.orchestra.models import IssueInfo, Trigger
from vibe3.orchestra.router import Router


class Poller:
    """Polls GitHub for label changes and triggers commands asynchronously."""

    def __init__(self, config: OrchestraConfig):
        self.config = config
        self.router = Router()
        self.dispatcher = Dispatcher(config, dry_run=config.dry_run)
        self._state_cache: dict[int, IssueState | None] = {}
        self._seen_issues: set[int] = set()
        self._active_tasks: set[asyncio.Task] = set()
        self._semaphore: asyncio.Semaphore | None = None
        self._running = False
        self._executor = ThreadPoolExecutor(max_workers=config.max_concurrent_flows)
        self._master_handler = MasterAgentHandler(config, self._executor)

    def start(self) -> None:
        """Start the polling loop."""
        self._running = True
        self._write_pid()

        log = logger.bind(domain="orchestra", action="start")
        log.info(
            f"Starting Orchestra server (interval: {self.config.polling_interval}s, "
            f"max_concurrent: {self.config.max_concurrent_flows})"
        )

        try:
            asyncio.run(self._run_loop())
        except KeyboardInterrupt:
            log.info("Shutting down Orchestra server")
        finally:
            self._cleanup()

    async def _run_loop(self) -> None:
        """Async polling loop."""
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent_flows)

        while self._running:
            try:
                await self._tick_async()
                self._reap_completed_tasks()
            except Exception as e:
                logger.bind(domain="orchestra").error(f"Tick failed: {e}")

            await asyncio.sleep(self.config.polling_interval)

    def stop(self) -> None:
        """Stop the polling loop."""
        self._running = False
        for task in self._active_tasks:
            task.cancel()
        self._executor.shutdown(wait=False)

    async def _tick_async(self) -> None:
        """Single polling iteration with async dispatch."""
        log = logger.bind(domain="orchestra", action="tick")

        issues = self._fetch_issues()
        log.debug(f"Found {len(issues)} open issues")

        for issue in issues:
            await self._process_issue_async(issue)

    async def _process_issue_async(self, issue: IssueInfo) -> None:
        """Process a single issue asynchronously."""
        previous_state = self._state_cache.get(issue.number)

        if issue.state is None and issue.number not in self._seen_issues:
            if self.config.master_agent.enabled:
                task = asyncio.create_task(self._handle_new_issue_with_semaphore(issue))
                self._active_tasks.add(task)
            self._seen_issues.add(issue.number)

        elif issue.state and previous_state != issue.state:
            trigger = self.router.route(issue, previous_state)
            if trigger:
                prev = previous_state.value if previous_state else "none"
                curr = issue.state.value if issue.state else "none"
                logger.bind(domain="orchestra").info(
                    f"State change: #{issue.number} {prev} -> {curr}"
                )
                task = asyncio.create_task(
                    self._dispatch_with_semaphore(trigger, issue.number)
                )
                self._active_tasks.add(task)

        self._state_cache[issue.number] = issue.state

    async def _dispatch_with_semaphore(
        self, trigger: Trigger, issue_number: int
    ) -> None:
        """Dispatch with semaphore to limit concurrency."""
        if self._semaphore is None:
            return

        async with self._semaphore:
            log = logger.bind(domain="orchestra", issue=issue_number)
            log.info(f"Starting dispatch for issue #{issue_number}")
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    self._executor, self.dispatcher.dispatch, trigger
                )
                log.info(f"Dispatch completed for issue #{issue_number}")
            except asyncio.CancelledError:
                log.info(f"Dispatch cancelled for issue #{issue_number}")
            except Exception as e:
                log.error(f"Dispatch failed for issue #{issue_number}: {e}")

    async def _handle_new_issue_with_semaphore(self, issue: IssueInfo) -> None:
        """Handle new issue with semaphore to limit concurrency."""
        if self._semaphore is None:
            return

        async with self._semaphore:
            loop = asyncio.get_event_loop()
            decision = await loop.run_in_executor(
                self._executor, self._master_handler.handle, issue
            )
            if decision:
                await loop.run_in_executor(
                    self._executor,
                    self._master_handler.execute_decision,
                    issue.number,
                    decision,
                )

    def _reap_completed_tasks(self) -> None:
        """Remove completed tasks from tracking."""
        done_tasks = {t for t in self._active_tasks if t.done()}
        self._active_tasks -= done_tasks

        for task in done_tasks:
            try:
                task.result()
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.bind(domain="orchestra").error(f"Task failed: {e}")

    def _fetch_issues(self) -> list[IssueInfo]:
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
        self._executor.shutdown(wait=False)
