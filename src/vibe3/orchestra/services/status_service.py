"""OrchestraStatusService: aggregate read-only status for orchestra system."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.github_issues_ops import parse_blocked_by
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.queue_ordering import (
    resolve_priority,
    resolve_roadmap_rank,
    sort_ready_issues,
)
from vibe3.services.flow_reader import FlowReader
from vibe3.services.label_service import LabelService
from vibe3.services.status_query_service import issue_priority

if TYPE_CHECKING:
    from vibe3.runtime.circuit_breaker import CircuitBreaker


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
    # Queue metadata fields
    milestone: str | None = None
    roadmap: str | None = None
    priority: int = 0
    queue_rank: int | None = None


@dataclass(frozen=True)
class OrchestraSnapshot:
    """Frozen snapshot of Orchestra system state."""

    timestamp: float
    server_running: bool
    active_issues: tuple[IssueStatusEntry, ...]
    active_flows: int
    active_worktrees: int
    queued_issues: tuple[int, ...] = ()
    circuit_breaker_state: str = "closed"
    circuit_breaker_failures: int = 0
    circuit_breaker_last_failure: float | None = None
    dispatch_blocked: bool = False
    blocked_reason: str | None = None
    blocked_issue_number: int | None = None
    blocked_issue_reason: str | None = None


def format_issue_summary_line(entry: IssueStatusEntry) -> str:
    """Format issue summary line for governance reports."""
    state_label = entry.state.to_label() if entry.state else "state/unknown"
    blocked_by = ", ".join(f"#{number}" for number in entry.blocked_by)
    blocked = f" [blocked_by={blocked_by}]" if entry.blocked_by else ""
    return f"- #{entry.number}: {entry.title[:60]} | {state_label}{blocked}"


def format_issue_runtime_line(entry: IssueStatusEntry) -> str:
    """Format issue runtime line for governance detailed reports."""
    state_label = entry.state.to_label() if entry.state else "state/unknown"
    flow_value = entry.flow_branch or "(not started)"
    worktree_value = entry.worktree_path or "(none)"
    pr_value = f"#{entry.pr_number}" if entry.pr_number is not None else "(none)"
    parts = [
        f"- #{entry.number}: {entry.title[:60]}",
        state_label,
        f"assignee={entry.assignee or '(unassigned)'}",
        f"flow={flow_value}",
        f"worktree={worktree_value}",
        f"pr={pr_value}",
    ]
    if entry.blocked_by:
        blocked_by = ", ".join(f"#{number}" for number in entry.blocked_by)
        parts.append(f"blocked_by={blocked_by}")
    return " | ".join(parts)


def is_running_issue(entry: IssueStatusEntry) -> bool:
    """Check if issue has active runtime resources."""
    return entry.has_flow or entry.has_worktree or entry.has_pr


class OrchestraStatusService:
    """Aggregate read-only status from multiple data sources.

    Data sources:
    - GitHub Issues (via GitHubClient)
    - State labels (via LabelService)
    - Flow state (via FlowManager)
    - Worktrees (via GitClient)
    - Circuit Breaker (via CircuitBreaker)
    """

    def __init__(
        self,
        config: OrchestraConfig,
        github: GitHubClient | None = None,
        orchestrator: FlowReader | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        failed_gate: Any | None = None,
    ) -> None:
        self.config = config
        self._github = github or GitHubClient()

        # Internal orchestrator (FlowManager)
        if orchestrator is None:
            raise ValueError(
                "orchestrator must be provided; "
                "pass a FlowReader-compatible object (e.g. FlowManager)"
            )
        self._orchestrator = orchestrator

        self._circuit_breaker = circuit_breaker
        self._git = GitClient()
        self._label_service = LabelService(repo=config.repo)
        self._failed_gate = failed_gate

    @classmethod
    def fetch_live_snapshot(cls, config: OrchestraConfig) -> OrchestraSnapshot | None:
        """Attempt to fetch live snapshot from the running HTTP server."""
        import json
        import urllib.request
        from urllib.error import URLError

        url = f"http://127.0.0.1:{config.port}/status"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=1.0) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    # Reconstruct frozen dataclass
                    entries = [
                        IssueStatusEntry(**item)
                        for item in data.get("active_issues", [])
                    ]
                    return OrchestraSnapshot(
                        timestamp=data.get("timestamp", 0.0),
                        server_running=data.get("server_running", True),
                        active_issues=tuple(entries),
                        active_flows=data.get("active_flows", 0),
                        active_worktrees=data.get("active_worktrees", 0),
                        queued_issues=tuple(data.get("queued_issues", [])),
                        circuit_breaker_state=data.get(
                            "circuit_breaker_state", "closed"
                        ),
                        circuit_breaker_failures=data.get(
                            "circuit_breaker_failures", 0
                        ),
                        circuit_breaker_last_failure=data.get(
                            "circuit_breaker_last_failure"
                        ),
                        dispatch_blocked=data.get("dispatch_blocked", False),
                        blocked_reason=data.get("blocked_reason"),
                        blocked_issue_number=data.get("blocked_issue_number"),
                        blocked_issue_reason=data.get("blocked_issue_reason"),
                    )
                return None
        except (URLError, ConnectionError, Exception):
            return None

    def snapshot(self, queued: set[int] | None = None) -> OrchestraSnapshot:
        """Build current status snapshot."""
        log = logger.bind(domain="orchestra", action="status_snapshot")
        log.debug("Building orchestra status snapshot")

        # Get issues assigned to manager usernames
        issues = self._get_manager_issues()
        worktrees = self._get_worktree_map()

        # Build status entries
        entries: list[IssueStatusEntry] = []
        active_flows = 0

        # First pass: collect all ready issues for sorting
        ready_issues_data: list[dict[str, Any]] = []
        other_issues_data: list[dict[str, Any]] = []

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

            # Parse queue metadata
            labels = [
                label.get("name", "")
                for label in issue.get("labels", [])
                if isinstance(label, dict) and "name" in label
            ]

            # Extract milestone from GitHub milestone field
            milestone = None
            milestone_data = issue.get("milestone")
            if isinstance(milestone_data, dict) and "title" in milestone_data:
                milestone = milestone_data["title"]

            # Resolve priority and roadmap
            priority = resolve_priority(labels)
            _, roadmap = resolve_roadmap_rank(labels)

            # Collect issue data
            issue_data = {
                "number": number,
                "title": title,
                "state": state,
                "assignee": assignee,
                "has_flow": has_flow,
                "flow_branch": flow_branch,
                "has_worktree": has_worktree,
                "worktree_path": worktree_path,
                "has_pr": has_pr,
                "pr_number": pr_number,
                "blocked_by": tuple(blocked_by_list),
                "milestone": milestone,
                "roadmap": roadmap,
                "priority": priority,
                "labels": labels,
            }

            if state == IssueState.READY:
                ready_issues_data.append(issue_data)
            else:
                other_issues_data.append(issue_data)

        # Sort ready issues and assign real queue ranks
        ready_issue_infos = [
            IssueInfo(
                number=data["number"],
                title=data["title"],
                state=data["state"],
                labels=data["labels"],
                assignees=[data["assignee"]] if data["assignee"] else [],
                milestone=data["milestone"],
            )
            for data in ready_issues_data
        ]
        sorted_ready_infos = sort_ready_issues(ready_issue_infos)

        # Create sorted ready issue data with real queue ranks
        sorted_ready_data = []
        for rank, issue_info in enumerate(sorted_ready_infos, start=1):
            # Find matching issue_data
            matching_data = next(
                (d for d in ready_issues_data if d["number"] == issue_info.number),
                None,
            )
            if matching_data:
                matching_data["queue_rank"] = rank
                sorted_ready_data.append(matching_data)

        other_issues_data.sort(
            key=lambda item: (
                *(
                    issue_priority(item["state"])
                    if isinstance(item["state"], IssueState)
                    else (4, "unknown")
                ),
                item["number"],
            )
        )

        # Combine: ready issues first (sorted with real ranks), then others
        all_issues_data = sorted_ready_data + other_issues_data

        # Build final entries
        for data in all_issues_data:
            entries.append(
                IssueStatusEntry(
                    number=data["number"],
                    title=data["title"],
                    state=data["state"],
                    assignee=data["assignee"],
                    has_flow=data["has_flow"],
                    flow_branch=data["flow_branch"],
                    has_worktree=data["has_worktree"],
                    worktree_path=data["worktree_path"],
                    has_pr=data["has_pr"],
                    pr_number=data["pr_number"],
                    blocked_by=data["blocked_by"],
                    milestone=data["milestone"],
                    roadmap=data["roadmap"],
                    priority=data["priority"],
                    queue_rank=data.get("queue_rank"),
                )
            )

        # Check failed gate
        dispatch_blocked = False
        blocked_reason = None
        blocked_issue_number = None
        blocked_issue_reason = None
        if self._failed_gate:
            gate_result = self._failed_gate.check()
            if gate_result.blocked:
                dispatch_blocked = True
                blocked_reason = "state/failed"
                blocked_issue_number = gate_result.issue_number
                blocked_issue_reason = gate_result.reason

        snapshot = OrchestraSnapshot(
            timestamp=time.time(),
            server_running=True,
            active_issues=tuple(entries),
            active_flows=active_flows,
            active_worktrees=len(worktrees),
            queued_issues=tuple(queued) if queued else (),
            circuit_breaker_state=self._get_circuit_breaker_state(),
            circuit_breaker_failures=self._get_circuit_breaker_failures(),
            circuit_breaker_last_failure=self._get_circuit_breaker_last_failure(),
            dispatch_blocked=dispatch_blocked,
            blocked_reason=blocked_reason,
            blocked_issue_number=blocked_issue_number,
            blocked_issue_reason=blocked_issue_reason,
        )

        log.debug(
            f"Snapshot built: {len(entries)} issues, {active_flows} flows, "
            f"{len(worktrees)} worktrees"
        )
        return snapshot

    def _get_manager_issues(self) -> list[dict]:
        seen_numbers: set[int] = set()
        issues: list[dict] = []

        for username in self.config.manager_usernames:
            try:
                result = self._github.list_issues(
                    state="open",
                    assignee=username,
                    limit=50,
                    repo=self.config.repo,
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
        try:
            worktrees = self._git.list_worktrees()
            return {
                branch.removeprefix("refs/heads/"): path for path, branch in worktrees
            }
        except Exception as exc:
            logger.bind(domain="orchestra").warning(f"Failed to list worktrees: {exc}")
            return {}

    def get_active_flow_count(self) -> int:
        try:
            return self._orchestrator.get_active_flow_count()
        except Exception as exc:
            logger.bind(domain="orchestra").warning(
                f"Failed to count active flows: {exc}"
            )
            return 0

    def _get_circuit_breaker_state(self) -> str:
        if self._circuit_breaker:
            return self._circuit_breaker.state_value
        return "disabled"

    def _get_circuit_breaker_failures(self) -> int:
        if self._circuit_breaker:
            return self._circuit_breaker.failure_count
        return 0

    def _get_circuit_breaker_last_failure(self) -> float | None:
        if self._circuit_breaker and getattr(
            self._circuit_breaker, "last_failure_timestamp", None
        ):
            return self._circuit_breaker.last_failure_timestamp
        return None
