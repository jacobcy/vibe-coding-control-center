"""Flow orchestration utilities for orchestra dispatcher."""

import subprocess

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.models import IssueInfo


class FlowOrchestrator:
    """Manages issue-to-flow mapping and command execution."""

    def __init__(self, config: OrchestraConfig):
        self.config = config
        self.store = SQLiteClient()
        self.git = GitClient()

    def get_flow_for_issue(self, issue_number: int) -> dict | None:
        """Get flow linked to an issue."""
        flows = self.store.get_flows_by_issue(issue_number, role="task")
        return flows[0] if flows else None

    def create_flow_for_issue(self, issue: IssueInfo) -> dict:
        """Create a new flow for an issue with real git branch.

        Args:
            issue: Issue to create flow for

        Returns:
            Created flow data

        Raises:
            RuntimeError: If flow creation fails
        """
        log = logger.bind(
            domain="orchestra",
            action="create_flow",
            issue=issue.number,
        )

        existing = self.get_flow_for_issue(issue.number)
        if existing:
            log.info(f"Flow already exists for issue #{issue.number}")
            return existing

        slug = f"issue-{issue.number}"
        branch = f"task/{slug}"

        if self.git.branch_exists(branch):
            log.info(f"Branch '{branch}' already exists, binding to existing")
            self.store.add_issue_link(branch, issue.number, "task")
            self.store.update_flow_state(branch, task_issue_number=issue.number)
            return self.store.get_flow_state(branch) or {}

        current_branch = self.git.get_current_branch()

        try:
            self.git.create_branch(branch, start_ref="origin/main")
            self.git.switch_branch(branch)

            self.store.update_flow_state(branch, flow_slug=slug)
            self.store.add_issue_link(branch, issue.number, "task")
            self.store.update_flow_state(branch, task_issue_number=issue.number)

            log.info(
                f"Created flow '{slug}' with branch '{branch}' "
                f"for issue #{issue.number}"
            )
            return self.store.get_flow_state(branch) or {}

        except Exception as e:
            log.error(f"Failed to create flow: {e}")
            try:
                self.git.switch_branch(current_branch)
            except Exception:
                pass
            raise RuntimeError(f"Failed to create flow for issue #{issue.number}: {e}")

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
        flow = self.get_flow_for_issue(issue_number)
        if not flow:
            logger.bind(domain="orchestra").warning(
                f"No flow found for issue #{issue_number}"
            )
            return None

        branch: str | None = flow.get("branch")
        if not branch:
            logger.bind(domain="orchestra").warning(
                f"Flow for issue #{issue_number} has no branch"
            )
            return None

        if not self.git.branch_exists(branch):
            logger.bind(domain="orchestra").error(
                f"Branch '{branch}' does not exist for issue #{issue_number}"
            )
            return None

        current = self.git.get_current_branch()
        if current == branch:
            return str(branch)

        try:
            self.git.switch_branch(branch)
            logger.bind(domain="orchestra").info(
                f"Switched to branch '{branch}' for issue #{issue_number}"
            )
            return str(branch)
        except Exception as e:
            logger.bind(domain="orchestra").error(f"Failed to switch branch: {e}")
            return None
