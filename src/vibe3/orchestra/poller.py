"""GitHub label poller with async dispatch."""

import asyncio
import json
import subprocess

from loguru import logger

from vibe3.models.orchestration import IssueState
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.dispatcher import Dispatcher
from vibe3.orchestra.master import TriageDecision, run_master_agent
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
        self._active_tasks: dict[int, asyncio.Task] = {}
        self._running = False

    def start(self) -> None:
        """Start the polling loop."""
        self._running = True
        self._write_pid()

        log = logger.bind(domain="orchestra", action="start")
        log.info(
            f"Starting Orchestra daemon (interval: {self.config.polling_interval}s, "
            f"max_concurrent: {self.config.max_concurrent_flows})"
        )

        try:
            asyncio.run(self._run_loop())
        except KeyboardInterrupt:
            log.info("Shutting down Orchestra daemon")
        finally:
            self._cleanup()

    async def _run_loop(self) -> None:
        """Async polling loop."""
        while self._running:
            try:
                await self._tick_async()
            except Exception as e:
                logger.bind(domain="orchestra").error(f"Tick failed: {e}")

            await asyncio.sleep(self.config.polling_interval)

    def stop(self) -> None:
        """Stop the polling loop."""
        self._running = False
        for task in self._active_tasks.values():
            task.cancel()

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
                await self._handle_new_issue_async(issue)
            self._seen_issues.add(issue.number)

        elif issue.state and previous_state != issue.state:
            active_count = len(self._active_tasks)
            if active_count >= self.config.max_concurrent_flows:
                log = logger.bind(domain="orchestra")
                log.warning(
                    f"Max concurrent ({self.config.max_concurrent_flows}) "
                    f"reached, skipping #{issue.number}"
                )
                return

            trigger = self.router.route(issue, previous_state)
            if trigger:
                prev = previous_state.value if previous_state else "none"
                curr = issue.state.value if issue.state else "none"
                logger.bind(domain="orchestra").info(
                    f"State change: #{issue.number} {prev} -> {curr}"
                )
                await self._dispatch_async(trigger, issue.number)

        self._state_cache[issue.number] = issue.state

    async def _dispatch_async(self, trigger: Trigger, issue_number: int) -> None:
        """Dispatch trigger asynchronously."""
        task = asyncio.create_task(self._run_dispatch(trigger, issue_number))
        self._active_tasks[issue_number] = task

        try:
            await task
        except asyncio.CancelledError:
            logger.bind(domain="orchestra").info(f"Task for #{issue_number} cancelled")
        except Exception as e:
            logger.bind(domain="orchestra").error(
                f"Task for #{issue_number} failed: {e}"
            )
        finally:
            self._active_tasks.pop(issue_number, None)

    async def _run_dispatch(self, trigger: Trigger, issue_number: int) -> None:
        """Run dispatch in executor to avoid blocking."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.dispatcher.dispatch, trigger)

    async def _handle_new_issue_async(self, issue: IssueInfo) -> None:
        """Handle new issue without state label using master agent."""
        log = logger.bind(
            domain="orchestra",
            action="master",
            issue=issue.number,
        )
        log.info(f"New issue detected: #{issue.number} - {issue.title}")

        issue_data = await self._fetch_issue_details_async(issue.number)
        if not issue_data:
            log.error(f"Failed to fetch issue #{issue.number}")
            return

        loop = asyncio.get_event_loop()
        options = self.config.master_agent.to_agent_options()

        decision = await loop.run_in_executor(
            None,
            lambda: run_master_agent(
                issue=issue_data,
                repo=self.config.repo or "",
                options=options,
                dry_run=self.config.dry_run,
            ),
        )

        log.info(f"Master agent decision: {decision.action} - {decision.reason}")
        await self._execute_decision_async(issue.number, decision)

    async def _fetch_issue_details_async(self, issue_number: int) -> dict | None:
        """Fetch full issue details from GitHub asynchronously."""
        cmd = [
            "gh",
            "issue",
            "view",
            str(issue_number),
            "--json",
            "number,title,body,labels,url,createdAt,user",
        ]

        if self.config.repo:
            cmd.extend(["--repo", self.config.repo])

        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(cmd, capture_output=True, text=True, timeout=30),
            )

            if result.returncode != 0:
                return None

            return dict(json.loads(result.stdout))
        except Exception as e:
            logger.bind(domain="orchestra").error(f"Failed to fetch issue: {e}")
            return None

    async def _execute_decision_async(
        self, issue_number: int, decision: TriageDecision
    ) -> None:
        """Execute master agent decision asynchronously."""
        loop = asyncio.get_event_loop()

        if decision.action == "close":
            cmd = ["gh", "issue", "close", str(issue_number)]
            if self.config.repo:
                cmd.extend(["--repo", self.config.repo])
            if decision.comment_body:
                cmd.extend(["--comment", decision.comment_body])
            await loop.run_in_executor(
                None, lambda: subprocess.run(cmd, capture_output=True)
            )

        elif decision.action == "triage":
            cmd = [
                "gh",
                "issue",
                "edit",
                str(issue_number),
                "--add-label",
                "state/ready",
            ]
            if self.config.repo:
                cmd.extend(["--repo", self.config.repo])
            await loop.run_in_executor(
                None, lambda: subprocess.run(cmd, capture_output=True)
            )

        elif decision.action == "comment" and decision.comment_body:
            cmd = [
                "gh",
                "issue",
                "comment",
                str(issue_number),
                "--body",
                decision.comment_body,
            ]
            if self.config.repo:
                cmd.extend(["--repo", self.config.repo])
            await loop.run_in_executor(
                None, lambda: subprocess.run(cmd, capture_output=True)
            )

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
