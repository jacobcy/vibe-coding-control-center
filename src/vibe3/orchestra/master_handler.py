"""Master agent utilities for orchestra."""

import json
import subprocess
from concurrent.futures import ThreadPoolExecutor

from loguru import logger

from vibe3.models.orchestration import IssueState
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.master import TriageDecision, run_master_agent
from vibe3.orchestra.models import IssueInfo
from vibe3.services.label_service import LabelService


class MasterAgentHandler:
    """Handles master agent triage for new issues."""

    def __init__(self, config: OrchestraConfig, executor: ThreadPoolExecutor):
        self.config = config
        self.executor = executor

    def handle(self, issue: IssueInfo) -> TriageDecision | None:
        """Handle new issue with master agent.

        Returns:
            TriageDecision or None if failed
        """
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
        """Execute master agent decision."""
        if decision.action == "close":
            cmd = ["gh", "issue", "close", str(issue_number)]
            if self.config.repo:
                cmd.extend(["--repo", self.config.repo])
            if decision.comment_body:
                cmd.extend(["--comment", decision.comment_body])
            subprocess.run(cmd, capture_output=True)

        elif decision.action == "triage":
            LabelService(repo=self.config.repo).confirm_issue_state(
                issue_number,
                IssueState.READY,
                actor="orchestra:triage",
                force=True,
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
            subprocess.run(cmd, capture_output=True)

    def _fetch_issue_details(self, issue_number: int) -> dict | None:
        """Fetch full issue details from GitHub."""
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

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                return None

            return dict(json.loads(result.stdout))
        except Exception as e:
            logger.bind(domain="orchestra").error(f"Failed to fetch issue: {e}")
            return None
