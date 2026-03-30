"""GovernanceService: periodic governance scan via vibe-orchestra skill.

Runs governance skill periodically to:
- Adjust issue labels and priorities
- Analyze dependencies
- Assign ready issues to manager agent

The service does NOT make decisions itself - it builds context and invokes
the skill, which makes decisions through GitHub API (label/assignee changes).
"""

from __future__ import annotations

import asyncio
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from loguru import logger

from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.event_bus import GitHubEvent, ServiceBase
from vibe3.orchestra.services.status_service import (
    OrchestraSnapshot,
    OrchestraStatusService,
)


class GovernanceService(ServiceBase):
    """Periodic governance scan service.

    Runs governance skill on a configurable interval to maintain
    issue queue health. Does not handle webhook events - only tick-based.
    """

    event_types: list[str] = []  # No webhook events, tick-based only

    def __init__(
        self,
        config: OrchestraConfig,
        status_service: OrchestraStatusService,
        executor: ThreadPoolExecutor | None = None,
        governance_interval: int = 4,
    ) -> None:
        """Initialize governance service.

        Args:
            config: Orchestra configuration
            status_service: Status service for snapshots
            executor: Thread pool for subprocess execution
            governance_interval: Run governance every N ticks
        """
        self.config = config
        self._status_service = status_service
        self._executor = executor or ThreadPoolExecutor(max_workers=1)
        self._tick_count = 0
        self._governance_interval = governance_interval
        self._last_run_time: float = 0.0

    async def handle_event(self, event: GitHubEvent) -> None:
        """No-op: governance service is tick-based only."""
        pass

    async def on_tick(self) -> None:
        """Run governance scan on interval."""
        self._tick_count += 1

        if self._tick_count % self._governance_interval != 0:
            return

        log = logger.bind(domain="orchestra", action="governance")
        log.info(f"Running governance scan (tick #{self._tick_count})")

        try:
            await self._run_governance()
        except Exception as exc:
            log.error(f"Governance scan failed: {exc}")

    async def _run_governance(self) -> None:
        """Execute governance scan.

        1. Get current status snapshot
        2. Build governance plan
        3. Execute via vibe3 run --plan
        """
        log = logger.bind(domain="orchestra", action="governance")

        # 1. Get snapshot
        snapshot = await asyncio.get_running_loop().run_in_executor(
            self._executor, self._status_service.snapshot
        )

        # 2. Check circuit breaker - skip governance if breaker is open
        if snapshot.circuit_breaker_state == "open":
            log.warning("Skipping governance: circuit breaker is OPEN")
            return

        # 3. Build plan
        plan_content = self._build_governance_plan(snapshot)

        if self.config.dry_run:
            log.info("Dry run: would execute governance plan:")
            log.info(f"\n{plan_content}")
            return

        # 4. Write to temp file and execute
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as plan_file:
            plan_file.write(plan_content)
            plan_path = Path(plan_file.name)

        try:
            cmd = [
                "uv",
                "run",
                "python",
                "-m",
                "vibe3",
                "run",
                "--plan",
                str(plan_path),
            ]
            log.info(f"Executing: {' '.join(cmd)}")

            result = await asyncio.get_running_loop().run_in_executor(
                self._executor,
                lambda: self._execute_command(cmd),
            )

            if result:
                log.info("Governance scan completed successfully")
            else:
                log.warning("Governance scan returned non-zero exit code")
        finally:
            # Cleanup temp file
            plan_path.unlink(missing_ok=True)

    def _execute_command(self, cmd: list[str]) -> bool:
        """Execute command synchronously."""
        import subprocess

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout
            )
            if result.returncode != 0:
                logger.bind(domain="orchestra", action="governance").error(
                    f"Command failed: {result.stderr}"
                )
                return False
            return True
        except subprocess.TimeoutExpired:
            logger.bind(domain="orchestra", action="governance").error(
                "Command timed out"
            )
            return False
        except Exception as exc:
            logger.bind(domain="orchestra", action="governance").error(
                f"Command error: {exc}"
            )
            return False

    def _build_governance_plan(self, snapshot: OrchestraSnapshot) -> str:
        """Build governance plan content from snapshot.

        Args:
            snapshot: Current orchestra status snapshot

        Returns:
            Markdown content for governance plan
        """
        lines = [
            "# Orchestra Governance Scan",
            "",
            "## System Status",
            "",
            f"- **Active Issues**: {len(snapshot.active_issues)}",
            f"- **Active Flows**: {snapshot.active_flows}",
            f"- **Active Worktrees**: {snapshot.active_worktrees}",
            f"- **Circuit Breaker**: {snapshot.circuit_breaker_state}",
            "",
            "## Issue Queue",
            "",
        ]

        if snapshot.active_issues:
            lines.append("| # | Title | State | Assignee | Flow | Blocked By |")
            lines.append("|---|-------|-------|----------|------|------------|")

            for issue in snapshot.active_issues[:20]:  # Limit to 20 issues
                state = issue.state.value if issue.state else "unknown"
                assignee = issue.assignee or "-"
                flow = "✓" if issue.has_flow else "-"
                blocked = (
                    ", ".join(f"#{b}" for b in issue.blocked_by)
                    if issue.blocked_by
                    else "-"
                )
                lines.append(
                    f"| #{issue.number} | {issue.title[:40]} | {state} | "
                    f"{assignee} | {flow} | {blocked} |"
                )
        else:
            lines.append("No active issues assigned to manager usernames.")

        lines.extend(
            [
                "",
                "## Instructions",
                "",
                "Execute `vibe-orchestra governance` workflow:",
                "",
                "1. **Priority Review**: Ensure issues have appropriate "
                "priority labels",
                "2. **Dependency Check**: Verify blocked_by issues are resolved",
                "3. **Assignment**: For READY issues without flow, assign to "
                "vibe-manager-agent",
                "4. **Cleanup**: Close or unassign stale issues",
                "",
                "Use `gh issue edit` to make changes. Changes will trigger "
                "webhook events",
                "that dispatch manager agents automatically.",
                "",
            ]
        )

        return "\n".join(lines)
