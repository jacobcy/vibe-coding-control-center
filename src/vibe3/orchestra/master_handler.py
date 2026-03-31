"""Master agent utilities for orchestra."""

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.master import TriageDecision, run_master_agent
from vibe3.services.label_service import LabelService


class MasterAgentHandler:
    """Handles master agent triage for new issues."""

    def __init__(self, config: OrchestraConfig, executor: ThreadPoolExecutor) -> None:
        self.config = config
        self.executor = executor
        self._github = GitHubClient()

    def handle(self, issue: IssueInfo) -> TriageDecision | None:
        """Handle new issue with master agent."""
        log = logger.bind(
            domain="orchestra",
            action="master",
            issue=issue.number,
        )
        log.info(f"New issue detected: #{issue.number} - {issue.title}")

        issue_data = self._fetch_issue_details(issue.number)
        if not issue_data:
            log.error(f"Failed to fetch issue #{issue.number}")
            return None

        options = self.config.master_agent.to_agent_options()

        decision = run_master_agent(
            issue=issue_data,
            repo=self.config.repo or "",
            options=options,
            dry_run=self.config.dry_run,
        )

        log.info(f"Master agent decision: {decision.action} - {decision.reason}")
        return decision

    def execute_decision(self, issue_number: int, decision: TriageDecision) -> None:
        """Execute master agent decision using GitHubClient."""
        if decision.action == "close":
            self._github.close_issue(
                issue_number,
                comment=decision.comment_body,
                repo=self.config.repo,
            )

        elif decision.action == "triage":
            LabelService(repo=self.config.repo).confirm_issue_state(
                issue_number,
                IssueState.READY,
                actor="orchestra:triage",
                force=True,
            )

        elif decision.action == "comment" and decision.comment_body:
            self._github.add_comment(
                issue_number,
                body=decision.comment_body,
                repo=self.config.repo,
            )

    def _fetch_issue_details(self, issue_number: int) -> dict[str, Any] | None:
        """Fetch issue details via GitHubClient."""
        data = self._github.view_issue(issue_number)
        if not data or data == "network_error":
            return None
        if isinstance(data, dict):
            return data
        return None
