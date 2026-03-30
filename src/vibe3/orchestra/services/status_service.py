"""OrchestraStatusService: aggregate read-only status for orchestra system."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.github_issues_ops import parse_blocked_by
from vibe3.models.orchestration import IssueState
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.flow_orchestrator import FlowOrchestrator
from vibe3.services.label_service import LabelService

if TYPE_CHECKING:
    from vibe3.orchestra.circuit_breaker import CircuitBreaker


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
    blocked_by: tuple[int, ...] = ()


@dataclass(frozen=True)
class OrchestraSnapshot:
    """Frozen snapshot of Orchestra system state."""

    timestamp: float
    server_running: bool
    active_issues: tuple[IssueStatusEntry, ...]
    active_flows: int
    active_worktrees: int
    circuit_breaker_state: str = "closed"
    circuit_breaker_failures: int = 0
    circuit_breaker_last_failure: float | None = None


class OrchestraStatusService:
    """Aggregate read-only status from multiple data sources.

    Does not register as ServiceBase (no event handling needed).
    Provides snapshot() for CLI and HTTP endpoint.

    Data sources:
    - GitHub Issues (via GitHubClient)
    - State labels (via LabelService)
    - Flow state (via FlowOrchestrator)
    - Worktrees (via GitClient)
    - Circuit Breaker (via CircuitBreaker)
    """

    def __init__(
        self,
        config: OrchestraConfig,
        github: GitHubClient | None = None,
        orchestrator: FlowOrchestrator | None = None,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        self.config = config
        self._github = github or GitHubClient()
        self._orchestrator = orchestrator or FlowOrchestrator(config)
        self._circuit_breaker = circuit_breaker
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

            # Parse blocked_by from issue body
            blocked_by_list = parse_blocked_by(issue.get("body") or "")

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
                    blocked_by=tuple(blocked_by_list),
                )
            )

        snapshot = OrchestraSnapshot(
            timestamp=time.time(),
            server_running=True,  # If we're here, server is running
            active_issues=tuple(entries),
            active_flows=active_flows,
            active_worktrees=len(worktrees),
            circuit_breaker_state=self._get_circuit_breaker_state(),
            circuit_breaker_failures=self._get_circuit_breaker_failures(),
            circuit_breaker_last_failure=self._get_circuit_breaker_last_failure(),
        )

        log.debug(
            f"Snapshot built: {len(entries)} issues, {active_flows} flows, "
            f"{len(worktrees)} worktrees"
        )
        return snapshot

    def _get_manager_issues(self) -> list[dict]:
        """Get open issues assigned to manager usernames.

        Deduplicates issues by number to avoid counting the same issue
        multiple times when assigned to multiple managers.
        """
        seen_numbers: set[int] = set()
        issues: list[dict] = []

        for username in self.config.manager_usernames:
            try:
                result = self._github.list_issues(
                    state="open",
                    assignee=username,
                    limit=50,
                )
                if not result:
                    continue
                for issue in result:
                    number = issue.get("number")
                    if number and number not in seen_numbers:
                        seen_numbers.add(number)
                        issues.append(issue)
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

    def _get_circuit_breaker_state(self) -> str:
        """Get current circuit breaker state."""
        if self._circuit_breaker:
            return self._circuit_breaker.state_value
        return "disabled"

    def _get_circuit_breaker_failures(self) -> int:
        """Get current circuit breaker failure count."""
        if self._circuit_breaker:
            return self._circuit_breaker.failure_count
        return 0

    def _get_circuit_breaker_last_failure(self) -> float | None:
        """Get the last failure timestamp."""
        if self._circuit_breaker and getattr(
            self._circuit_breaker, "last_failure_timestamp", None
        ):
            return self._circuit_breaker.last_failure_timestamp
        return None
