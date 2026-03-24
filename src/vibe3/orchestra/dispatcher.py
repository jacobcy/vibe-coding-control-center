"""Command dispatcher with flow orchestration."""

import asyncio
import subprocess
from pathlib import Path

from loguru import logger

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.models.orchestration import IssueState
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.models import IssueInfo, Trigger


class FlowOrchestrator:
    """Manages issue-to-flow mapping and command execution."""

    def __init__(self, config: OrchestraConfig):
        self.config = config
        self.store = SQLiteClient()

    def get_flow_for_issue(self, issue_number: int) -> dict | None:
        """Get flow linked to an issue."""
        flows = self.store.get_flows_by_issue(issue_number, role="task")
        return flows[0] if flows else None

    def create_flow_for_issue(self, issue: IssueInfo) -> dict:
        """Create a new flow for an issue.

        Args:
            issue: Issue to create flow for

        Returns:
            Created flow data
        """
        from vibe3.services.flow_service import FlowService

        log = logger.bind(
            domain="orchestra",
            action="create_flow",
            issue=issue.number,
        )

        existing = self.get_flow_for_issue(issue.number)
        if existing:
            log.info(f"Flow already exists for issue #{issue.number}")
            return existing

        flow_service = FlowService(self.store)
        slug = f"issue-{issue.number}"
        branch = f"task/{slug}"

        try:
            flow_service.create_flow(slug, branch)
            self.store.add_issue_link(branch, issue.number, "task")
            self.store.update_flow_state(branch, task_issue_number=issue.number)

            log.info(f"Created flow '{slug}' for issue #{issue.number}")
            return self.store.get_flow_state(branch) or {}
        except Exception as e:
            log.error(f"Failed to create flow: {e}")
            raise

    def get_pr_for_issue(self, issue_number: int) -> int | None:
        """Get PR number for an issue.

        Priority:
        1. PR stored in flow state
        2. Query GitHub for PR with closing keyword
        """
        flow = self.get_flow_for_issue(issue_number)
        if flow and flow.get("pr_number"):
            return int(flow["pr_number"])

        cmd = [
            "gh",
            "pr",
            "list",
            "--state",
            "all",
            "--json",
            "number,closingIssuesReferences",
            "--limit",
            "10",
        ]
        if self.config.repo:
            cmd.extend(["--repo", self.config.repo])

        try:
            import json

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                prs = json.loads(result.stdout)
                for pr in prs:
                    refs = pr.get("closingIssuesReferences", [])
                    for ref in refs:
                        if ref.get("number") == issue_number:
                            return int(pr["number"])
        except Exception as e:
            logger.bind(domain="orchestra").error(f"Failed to get PR: {e}")

        return None

    def switch_to_flow_branch(self, issue_number: int) -> str | None:
        """Switch to the branch for a flow.

        Returns:
            Branch name if successful, None otherwise
        """
        from vibe3.clients.git_client import GitClient

        flow = self.get_flow_for_issue(issue_number)
        if not flow:
            return None

        branch = flow.get("branch")
        if not branch:
            return None

        return str(branch)

        git = GitClient()
        if git.get_current_branch() == branch:
            return branch

        try:
            git.switch_branch(branch)
            return branch
        except Exception as e:
            logger.bind(domain="orchestra").error(f"Failed to switch branch: {e}")
            return None


class Dispatcher:
    """Dispatches commands based on triggers with flow orchestration."""

    def __init__(
        self,
        config: OrchestraConfig,
        dry_run: bool = False,
        repo_path: Path | None = None,
    ):
        self.config = config
        self.dry_run = dry_run
        self.repo_path = repo_path or Path.cwd()
        self.orchestrator = FlowOrchestrator(config)

    def dispatch(self, trigger: Trigger) -> bool:
        """Execute command for trigger with proper flow orchestration.

        Args:
            trigger: Trigger to dispatch

        Returns:
            True if successful, False otherwise
        """
        log = logger.bind(
            domain="orchestra",
            action="dispatch",
            issue=trigger.issue.number,
            command=trigger.command,
        )

        cmd = self._build_command(trigger)
        if cmd is None:
            log.error("Failed to build command")
            return False

        log.info(f"Dispatching: {' '.join(cmd)}")

        if self.dry_run:
            log.info("Dry run, skipping execution")
            return True

        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=3600,
            )

            if result.returncode != 0:
                log.error(f"Command failed: {result.stderr}")
                return False

            log.info("Command completed successfully")
            return True

        except subprocess.TimeoutExpired:
            log.error("Command timed out")
            return False
        except Exception as e:
            log.error(f"Command error: {e}")
            return False

    async def dispatch_async(self, trigger: Trigger) -> bool:
        """Execute command asynchronously.

        Args:
            trigger: Trigger to dispatch

        Returns:
            True if successful, False otherwise
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.dispatch, trigger)

    def _build_command(self, trigger: Trigger) -> list[str] | None:
        """Build command list from trigger with flow orchestration.

        Returns:
            Command list or None if build failed
        """
        issue = trigger.issue
        to_state = trigger.to_state

        cmd = ["uv", "run", "python", "-m", "vibe3"]
        cmd.append(trigger.command)
        cmd.extend(trigger.args)

        if trigger.command == "plan":
            return self._build_plan_command(cmd, issue, to_state)
        elif trigger.command == "run":
            return self._build_run_command(cmd, issue, to_state)
        elif trigger.command == "review":
            return self._build_review_command(cmd, issue, to_state)

        return None

    def _build_plan_command(
        self, cmd: list[str], issue: IssueInfo, to_state: IssueState
    ) -> list[str] | None:
        """Build plan command.

        For ready -> claimed:
        - Create flow for issue
        - Run plan task <issue_number>
        """
        if to_state != IssueState.CLAIMED:
            return None

        try:
            self.orchestrator.create_flow_for_issue(issue)
        except Exception:
            pass

        cmd.append(str(issue.number))
        return cmd

    def _build_run_command(
        self, cmd: list[str], issue: IssueInfo, to_state: IssueState
    ) -> list[str] | None:
        """Build run command.

        For claimed -> in_progress:
        - Switch to flow branch
        - Run execute
        """
        if to_state != IssueState.IN_PROGRESS:
            return None

        branch = self.orchestrator.switch_to_flow_branch(issue.number)
        if not branch:
            logger.bind(domain="orchestra").warning(
                f"No flow branch for issue #{issue.number}, run will use current branch"
            )

        return cmd

    def _build_review_command(
        self, cmd: list[str], issue: IssueInfo, to_state: IssueState
    ) -> list[str] | None:
        """Build review command.

        For in_progress -> review:
        - Get PR number for issue
        - Run review pr <pr_number>
        """
        if to_state != IssueState.REVIEW:
            return None

        pr_number = self.orchestrator.get_pr_for_issue(issue.number)
        if not pr_number:
            logger.bind(domain="orchestra").error(
                f"No PR found for issue #{issue.number}, cannot review"
            )
            return None

        cmd.append(str(pr_number))
        return cmd
