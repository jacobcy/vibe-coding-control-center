"""OrchestraStatusService: aggregate read-only status for orchestra system."""

from __future__ import annotations

import time
from dataclasses import dataclass

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.models.orchestration import IssueState
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.flow_orchestrator import FlowOrchestrator
from vibe3.services.label_service import LabelService


@dataclass(frozen=True)
class IssueStatusEntry:
    """Aggregated status for a single issue."""

    number: int
    title: str
    state: IssueState | None
    assignee: str | None
    has_flow: bool
    flow_branch: str | None
    has_worktree: bool
    worktree_path: str | None
    has_pr: bool
    pr_number: int | None


@dataclass(frozen=True)
class OrchestraSnapshot:
    """Frozen snapshot of Orchestra system state."""

    timestamp: float
    server_running: bool
    active_issues: tuple[IssueStatusEntry, ...]
    active_flows: int
    active_worktrees: int


class OrchestraStatusService:
    """Aggregate read-only status from multiple data sources.

    Does not register as ServiceBase (no event handling needed).
    Provides snapshot() for CLI and HTTP endpoint.

    Data sources:
    - GitHub Issues (via GitHubClient)
    - State labels (via LabelService)
    - Flow state (via FlowOrchestrator)
    - Worktrees (via GitClient)
    """

    def __init__(
        self,
        config: OrchestraConfig,
        github: GitHubClient | None = None,
        orchestrator: FlowOrchestrator | None = None,
    ) -> None:
        self.config = config
        self._github = github or GitHubClient()
        self._orchestrator = orchestrator or FlowOrchestrator(config)
        self._git = GitClient()
        self._label_service = LabelService(repo=config.repo)

    def snapshot(self) -> OrchestraSnapshot:
        """Build current status snapshot.

        Performs ~1-2 GitHub API calls (list issues + potentially get PRs).
        """
        log = logger.bind(domain="orchestra", action="status_snapshot")
        log.debug("Building orchestra status snapshot")

        # Get issues assigned to manager usernames
        issues = self._get_manager_issues()
        worktrees = self._get_worktree_map()

        # Build status entries
        entries: list[IssueStatusEntry] = []
        active_flows = 0

        for issue in issues:
            number = issue.get("number")
            if not number:
                continue

            title = issue.get("title", "")
            assignees = issue.get("assignees", [])
            assignee = assignees[0].get("login") if assignees else None

            # Get state from labels
            state = self._label_service.get_state(number)

            # Check flow
            flow = self._orchestrator.get_flow_for_issue(number)
            has_flow = flow is not None
            flow_branch = flow.get("branch") if flow else None
            if has_flow:
                active_flows += 1

            # Check worktree
            branch_name = flow_branch or f"task/issue-{number}"
            worktree_path = worktrees.get(branch_name)
            has_worktree = worktree_path is not None

            # Check PR
            pr_number = None
            has_pr = False
            if has_flow:
                pr_number = self._orchestrator.get_pr_for_issue(number)
                has_pr = pr_number is not None

            entries.append(
                IssueStatusEntry(
                    number=number,
                    title=title,
                    state=state,
                    assignee=assignee,
                    has_flow=has_flow,
                    flow_branch=flow_branch,
                    has_worktree=has_worktree,
                    worktree_path=worktree_path,
                    has_pr=has_pr,
                    pr_number=pr_number,
                )
            )

        snapshot = OrchestraSnapshot(
            timestamp=time.time(),
            server_running=True,  # If we're here, server is running
            active_issues=tuple(entries),
            active_flows=active_flows,
            active_worktrees=len(worktrees),
        )

        log.debug(
            f"Snapshot built: {len(entries)} issues, {active_flows} flows, "
            f"{len(worktrees)} worktrees"
        )
        return snapshot

    def _get_manager_issues(self) -> list[dict]:
        """Get open issues assigned to manager usernames."""
        issues: list[dict] = []
        for username in self.config.manager_usernames:
            try:
                result = self._github.list_issues(
                    state="open",
                    assignee=username,
                    limit=50,
                )
                if result:
                    issues.extend(result)
            except Exception as exc:
                logger.bind(domain="orchestra").warning(
                    f"Failed to list issues for {username}: {exc}"
                )
        return issues

    def _get_worktree_map(self) -> dict[str, str]:
        """Get mapping of branch name -> worktree path."""
        try:
            worktrees = self._git.list_worktrees()
            return {
                branch.removeprefix("refs/heads/"): path for path, branch in worktrees
            }
        except Exception as exc:
            logger.bind(domain="orchestra").warning(f"Failed to list worktrees: {exc}")
            return {}

    def format_snapshot(self, snapshot: OrchestraSnapshot) -> str:
        """Format snapshot for CLI output."""
        from datetime import datetime

        ts = datetime.fromtimestamp(snapshot.timestamp).strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            f"Orchestra Status ({ts})",
            f"Server: {'running' if snapshot.server_running else 'stopped'}",
            "",
            "Active Issues:",
        ]

        if not snapshot.active_issues:
            lines.append("  (none)")
        else:
            for entry in snapshot.active_issues:
                state_str = entry.state.to_label() if entry.state else "state/unknown"
                flow_str = (
                    f"flow={entry.flow_branch}" if entry.flow_branch else "flow=(none)"
                )
                title_short = (
                    entry.title[:30] + "..." if len(entry.title) > 30 else entry.title
                )
                lines.append(
                    f"  #{entry.number:<4} {title_short:<33} {state_str:<18} {flow_str}"
                )

        lines.extend(
            [
                "",
                f"Flows: {snapshot.active_flows} active",
                f"Worktrees: {snapshot.active_worktrees} total",
            ]
        )

        return "\n".join(lines)
