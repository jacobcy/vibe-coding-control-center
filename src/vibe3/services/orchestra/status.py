"""OrchestraStatusService: aggregate read-only status for orchestra system."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from loguru import logger

from vibe3.clients import (
    FlowReader,
    GitClient,
    GitHubClient,
    GitHubClientProtocol,
)
from vibe3.config import get_manager_usernames
from vibe3.models import IssueState, OrchestraConfig
from vibe3.observability import orchestra_events_log_path
from vibe3.services.pr.service import PRService
from vibe3.services.shared.status_pipeline import (
    IssueStatusAggregator,
)
from vibe3.services.shared.status_pipeline import (
    IssueStatusEntry as _IssueStatusEntry,
)

if TYPE_CHECKING:
    from vibe3.runtime import CircuitBreaker


# Backward-compat re-export: consumers import from orchestra.status
IssueStatusEntry = _IssueStatusEntry


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
        self._failed_gate = failed_gate

    @classmethod
    def fetch_live_snapshot(cls, config: OrchestraConfig) -> OrchestraSnapshot | None:
        """Attempt to fetch live snapshot from the running HTTP server."""
        import json
        import urllib.request
        from urllib.error import URLError

        url = f"http://127.0.0.1:{config.port}/api/orchestra"
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

        # Delegate aggregation to shared IssueStatusAggregator
        aggregator = IssueStatusAggregator(
            github=self._github,
            git=self._git,
            pr_service_factory=lambda **kw: PRService(
                github_client=cast(GitHubClientProtocol, self._github),
                git_client=self._git,
                store=getattr(self._orchestrator, "store", None),
                **kw,
            ),
            worktree_map_provider=None,  # Use aggregator's default implementation
            orchestrator=self._orchestrator,
        )

        # Aggregate issues (orchestra: read-only PR cache, no context-cache writes)
        entries = aggregator.aggregate(
            issues=issues,
            queued=queued or set(),
            sync_context_cache=False,  # Orchestra path: read-only PR cache hydration
        )

        # Compute tallies from entries
        active_flows = sum(1 for entry in entries if entry.has_flow)
        worktrees = aggregator.fetch_worktree_map()
        active_worktrees = len(worktrees)

        # Check failed gate
        dispatch_blocked = False
        blocked_reason = None
        blocked_issue_number = None
        blocked_issue_reason = None
        if self._failed_gate:
            gate_result = self._failed_gate.check()
            if gate_result.blocked:
                dispatch_blocked = True
                from vibe3.config import get_convention

                convention = get_convention()
                blocked_reason = convention.state_label(convention.blocked_label)
                blocked_issue_reason = gate_result.reason

        snapshot = OrchestraSnapshot(
            timestamp=time.time(),
            server_running=True,
            active_issues=entries,
            active_flows=active_flows,
            active_worktrees=active_worktrees,
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
            f"{active_worktrees} worktrees"
        )
        return snapshot

    def _get_manager_issues(self) -> list[dict]:
        seen_numbers: set[int] = set()
        issues: list[dict] = []

        for username in get_manager_usernames(self.config):
            try:
                # fmt: off
                result = self._github.list_issues(
                    state="open",
                    assignee=username,
                    limit=50,
                    repo=self.config.repo,
                    fields=["number", "title", "state", "labels",
                            "assignees", "milestone", "body"],
                )
                # fmt: on
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
