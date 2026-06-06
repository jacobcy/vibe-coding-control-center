"""OrchestraStatusService: aggregate read-only status for orchestra system."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from loguru import logger

from vibe3.clients import (
    GitClient,
    GitHubClient,
    GitHubClientProtocol,
    parse_blocked_by,
)
from vibe3.models import IssueState, OrchestraConfig
from vibe3.observability import orchestra_events_log_path
from vibe3.services.flow_reader import FlowReader
from vibe3.services.label_service import LabelService
from vibe3.services.orchestra_helpers import get_manager_usernames
from vibe3.services.pr_service import PRService
from vibe3.services.status_query_service import (
    extract_primary_assignee_login,
    extract_queue_metadata,
    is_orchestra_managed_flow_branch,
    issue_priority,
    sort_ready_issue_dicts,
)

if TYPE_CHECKING:
    from vibe3.runtime import CircuitBreaker


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
    polling_interval: int = OrchestraConfig.model_fields["polling_interval"].default
    port: int = OrchestraConfig.model_fields["port"].default
    log_path: str = ""


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


def _extract_state_from_labels(labels: list) -> IssueState | None:
    """Extract state from issue labels without API call.

    Args:
        labels: List of label dicts from GitHub issue response

    Returns:
        IssueState if state/* label found, None otherwise
    """
    for label in labels:
        name = label.get("name", "") if isinstance(label, dict) else str(label)
        state = IssueState.from_label(name)
        if state:
            return state
    return None


class OrchestraStatusService:
    """Aggregate read-only status from multiple data sources.

    Data sources:
    - GitHub Issues (via GitHubClient)
    - State labels (via LabelService)
    - Flow state (via execution flow dispatch service)
    - Worktrees (via GitClient)
    - Circuit Breaker (via CircuitBreaker)
    """

    @classmethod
    def create(
        cls,
        config: OrchestraConfig,
        github: GitHubClient | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        failed_gate: Any | None = None,
        git_client: GitClient | None = None,
    ) -> "OrchestraStatusService":
        """Factory method to create OrchestraStatusService with default orchestrator.

        This factory creates a FlowManager internally, avoiding the need for
        callers to import FlowManager from domain layer (breaking circular deps).

        Args:
            config: Orchestra configuration
            github: Optional GitHub client (default: new GitHubClient)
            circuit_breaker: Optional circuit breaker instance
            failed_gate: Optional failed gate instance
            git_client: Optional Git client (default: new GitClient)

        Returns:
            OrchestraStatusService instance with FlowManager as orchestrator
        """
        # Dynamic import to avoid static analysis detecting circular dependency
        import importlib

        flow_manager_module = importlib.import_module("vibe3.domain.flow_manager")
        FlowManager = flow_manager_module.FlowManager  # noqa: N806

        flow_manager = FlowManager(config)
        return cls(
            config=config,
            github=github,
            orchestrator=flow_manager,
            circuit_breaker=circuit_breaker,
            failed_gate=failed_gate,
            git_client=git_client,
        )

    def __init__(
        self,
        config: OrchestraConfig,
        github: GitHubClient | None = None,
        orchestrator: FlowReader | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        failed_gate: Any | None = None,
        git_client: GitClient | None = None,
    ) -> None:
        self.config = config
        self._github = github or GitHubClient()

        # Internal orchestrator (flow reader)
        if orchestrator is None:
            raise ValueError(
                "orchestrator must be provided; pass a FlowReader-compatible "
                "object (e.g. execution flow dispatch service) or use create() factory"
            )
        self._orchestrator = orchestrator

        self._circuit_breaker = circuit_breaker
        self._git = git_client or GitClient()
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
            with urllib.request.urlopen(req, timeout=3.0) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    # Reconstruct frozen dataclass with proper type coercion
                    entries = []
                    for item in data.get("active_issues", []):
                        # Convert state string back to IssueState enum
                        state_value = item.get("state")
                        state: IssueState | None = None
                        if state_value is not None:
                            try:
                                state = IssueState(state_value)
                            except ValueError:
                                pass  # Keep None for invalid states

                        entry = IssueStatusEntry(
                            number=int(item.get("number", 0)),
                            title=str(item.get("title", "")),
                            state=state,
                            assignee=item.get("assignee"),
                            has_flow=bool(item.get("has_flow", False)),
                            flow_branch=item.get("flow_branch"),
                            has_worktree=bool(item.get("has_worktree", False)),
                            worktree_path=item.get("worktree_path"),
                            has_pr=bool(item.get("has_pr", False)),
                            pr_number=item.get("pr_number"),
                            blocked_by=tuple(item.get("blocked_by", [])),
                            milestone=item.get("milestone"),
                            roadmap=item.get("roadmap"),
                            priority=int(item.get("priority", 0)),
                            queue_rank=item.get("queue_rank"),
                        )
                        entries.append(entry)

                    return OrchestraSnapshot(
                        timestamp=float(data.get("timestamp", 0.0)),
                        server_running=bool(data.get("server_running", True)),
                        active_issues=tuple(entries),
                        active_flows=int(data.get("active_flows", 0)),
                        active_worktrees=int(data.get("active_worktrees", 0)),
                        queued_issues=tuple(data.get("queued_issues", [])),
                        circuit_breaker_state=str(
                            data.get("circuit_breaker_state", "closed")
                        ),
                        circuit_breaker_failures=int(
                            data.get("circuit_breaker_failures", 0)
                        ),
                        circuit_breaker_last_failure=data.get(
                            "circuit_breaker_last_failure"
                        ),
                        dispatch_blocked=bool(data.get("dispatch_blocked", False)),
                        blocked_reason=data.get("blocked_reason"),
                        blocked_issue_number=data.get("blocked_issue_number"),
                        blocked_issue_reason=data.get("blocked_issue_reason"),
                        polling_interval=int(
                            data.get("polling_interval", config.polling_interval)
                        ),
                        port=int(data.get("port", config.port)),
                        log_path=str(data.get("log_path", "")),
                    )
                return None
        except (URLError, TimeoutError, ConnectionError, ValueError, TypeError):
            logger.bind(domain="orchestra").debug(
                "Live snapshot unavailable, falling back to static config"
            )
            return None

    def snapshot(self, queued: set[int] | None = None) -> OrchestraSnapshot:
        """Build current status snapshot for the assignee issue pool.

        The snapshot only includes assignee issues (issues assigned to manager
        usernames and managed by the manager chain). Supervisor issues are
        excluded as they are handled by supervisor/apply.
        """
        log = logger.bind(domain="orchestra", action="status_snapshot")
        log.debug("Building orchestra status snapshot")

        # Get issues assigned to manager usernames
        issues = self._get_manager_issues()
        worktrees = self._get_worktree_map()

        # First pass: collect issue rows and flow branches for batch PR lookup
        issue_rows: list[dict[str, Any]] = []
        flow_branches: set[str] = set()
        active_flows = 0

        for issue in issues:
            number = issue.get("number")
            if not number:
                continue

            title = issue.get("title", "")
            assignee = extract_primary_assignee_login(issue.get("assignees"))

            # Get state from issue labels (already fetched in list_issues)
            # Avoid N+1 API calls by not calling get_state() per issue
            state = _extract_state_from_labels(issue.get("labels", []))

            # Check flow
            flow = self._orchestrator.get_flow_for_issue(number)
            if flow and not is_orchestra_managed_flow_branch(flow.get("branch")):
                continue
            has_flow = flow is not None
            flow_branch = flow.get("branch") if flow else None
            if has_flow:
                active_flows += 1
                if flow_branch:
                    flow_branches.add(flow_branch)

            # Check worktree
            branch_name = flow_branch or f"task/issue-{number}"
            worktree_path = worktrees.get(branch_name)
            has_worktree = worktree_path is not None

            # Parse blocked_by from issue body
            blocked_by_list = parse_blocked_by(issue.get("body") or "")

            labels, milestone, priority, roadmap = extract_queue_metadata(
                issue.get("labels"),
                issue.get("milestone"),
            )

            # Skip supervisor issues - handled by supervisor/apply, not manager chain
            if "supervisor" in labels:
                continue

            issue_rows.append(
                {
                    "number": number,
                    "title": title,
                    "state": state,
                    "assignee": assignee,
                    "has_flow": has_flow,
                    "flow_branch": flow_branch,
                    "has_worktree": has_worktree,
                    "worktree_path": worktree_path,
                    "flow": flow,
                    "blocked_by": tuple(blocked_by_list),
                    "milestone": milestone,
                    "roadmap": roadmap,
                    "priority": priority,
                    "labels": labels,
                }
            )

        # Batch PR lookup: read-only cache hydration without context-cache writes
        branch_to_pr: dict[str, Any] = {}
        if flow_branches:
            try:
                pr_service = PRService(
                    github_client=cast(GitHubClientProtocol, self._github),
                    git_client=self._git,
                    store=getattr(self._orchestrator, "store", None),
                )
                all_prs = pr_service.refresh_recent_pr_cache(sync_context_cache=False)
                branch_to_pr = {
                    b: pr for b, pr in all_prs.items() if b in flow_branches
                }
            except Exception as exc:
                log.warning(f"Failed to batch hydrate PR status: {exc}")

        # Second pass: build issue data with PR info from batch lookup
        ready_issues_data: list[dict[str, Any]] = []
        other_issues_data: list[dict[str, Any]] = []

        for row in issue_rows:
            flow_branch = row["flow_branch"]
            flow = row["flow"]

            # Determine PR number from batch cache or stored flow value
            pr_number = None
            if row["has_flow"] and flow_branch:
                cached_pr = branch_to_pr.get(flow_branch)
                # Coerce pr_number to int if present (may be stored as string)
                pr_number_raw = flow.get("pr_number") if flow else None
                pr_number = cached_pr.number if cached_pr else None
                if pr_number is None and pr_number_raw:
                    try:
                        pr_number = int(pr_number_raw)
                    except (ValueError, TypeError):
                        pass  # Leave as None if conversion fails

            issue_data = {
                "number": row["number"],
                "title": row["title"],
                "state": row["state"],
                "assignee": row["assignee"],
                "has_flow": row["has_flow"],
                "flow_branch": row["flow_branch"],
                "has_worktree": row["has_worktree"],
                "worktree_path": row["worktree_path"],
                "has_pr": pr_number is not None,
                "pr_number": pr_number,
                "blocked_by": row["blocked_by"],
                "milestone": row["milestone"],
                "roadmap": row["roadmap"],
                "priority": row["priority"],
                "labels": row["labels"],
            }

            if row["state"] == IssueState.READY:
                ready_issues_data.append(issue_data)
            else:
                other_issues_data.append(issue_data)

        # Sort ready issues and assign real queue ranks
        sorted_ready_data = sort_ready_issue_dicts(ready_issues_data)

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
        entries: list[IssueStatusEntry] = []
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
                from vibe3.services.convention_resolver import ConventionResolver

                resolver = ConventionResolver.from_repo()
                convention = resolver.resolve()
                blocked_reason = convention.state_label(convention.blocked_label)
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
            polling_interval=self.config.polling_interval,
            port=self.config.port,
            log_path=str(orchestra_events_log_path()),
        )

        log.debug(
            f"Snapshot built: {len(entries)} issues, {active_flows} flows, "
            f"{len(worktrees)} worktrees"
        )
        return snapshot

    def _get_manager_issues(self) -> list[dict]:
        seen_numbers: set[int] = set()
        issues: list[dict] = []

        for username in get_manager_usernames(self.config):
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

    @staticmethod
    def get_manager_usernames(config: OrchestraConfig) -> tuple[str, ...]:
        """Get manager usernames for orchestra operations.

        This is a static method to allow usage without service instantiation.

        Args:
            config: OrchestraConfig instance

        Returns:
            Tuple of manager usernames (e.g., ('vibe-manager-agent',)).
        """
        return get_manager_usernames(config)

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
