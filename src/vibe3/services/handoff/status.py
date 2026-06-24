"""Handoff status aggregation service."""

import threading
from dataclasses import dataclass
from typing import Any

from vibe3.clients import BackendProtocol, GitClient, SQLiteClient
from vibe3.environment import SessionRegistryService
from vibe3.models import FlowEvent, FlowState, VerdictRecord
from vibe3.services.flow.service import FlowService
from vibe3.services.handoff.service import HandoffService
from vibe3.services.pr.verdict_service import VerdictService


@dataclass
class HandoffStatusResult:
    """Aggregated handoff status from multiple sources.

    Attributes:
        flow_slug: Flow identifier
        worktree_root: Worktree path for the branch
        state: Flow state from database
        events: List of successful handoff events
        latest_verdict: Latest verdict record if available
        live_sessions: List of truly live runtime sessions
        recent_updates: List of recent handoff file updates (append records)
    """

    flow_slug: str
    worktree_root: str | None
    state: FlowState
    events: list[FlowEvent]
    latest_verdict: VerdictRecord | None
    live_sessions: list[dict[str, Any]]
    recent_updates: list[dict[str, str]]


class HandoffStatusService:
    """Service for aggregating handoff status from multiple sources.

    This service encapsulates the status aggregation logic that was previously
    scattered across command layer (handoff_read.py), bringing together:
    - Flow state retrieval
    - Handoff events
    - Verdict lookup
    - Live session registry query
    - Worktree path resolution
    """

    _registry_lock = threading.Lock()

    store: SQLiteClient
    git_client: GitClient
    flow_service: FlowService
    handoff_service: HandoffService
    verdict_service: VerdictService
    session_registry: SessionRegistryService | None

    def __init__(
        self,
        store: SQLiteClient | None = None,
        git_client: GitClient | None = None,
        flow_service: FlowService | None = None,
        backend: BackendProtocol | None = None,
    ) -> None:
        """Initialize handoff status service.

        Args:
            store: SQLiteClient instance for database access
            git_client: GitClient instance for git operations
            flow_service: FlowService instance for flow operations
        """
        if store is not None:
            self.store = store
        elif flow_service is not None:
            self.store = flow_service.store
        else:
            self.store = SQLiteClient()
        self.git_client = git_client or GitClient()
        self.flow_service = flow_service or FlowService(
            store=self.store, git_client=self.git_client
        )
        self.handoff_service = HandoffService(store=self.store)
        self.verdict_service = VerdictService(store=self.store)

        # Backend is optional for read-only use cases:
        # - backend=None: SessionRegistryService assumes all tmux sessions exist
        #   (safe for status queries, but not capacity/dispatch logic)
        # - backend=CodeagentBackend(): Verifies actual tmux liveness
        self._backend = backend
        self.session_registry = None

    def get_handoff_status(
        self, branch: str, limit: int | None = 5
    ) -> HandoffStatusResult:
        """Aggregate handoff status from multiple sources.

        Args:
            branch: Target branch name
            limit: Maximum number of handoff events to retrieve (None = all)

        Returns:
            Aggregated handoff status result

        Raises:
            ValueError: If no flow exists for branch
        """
        state = self.flow_service.get_flow_state(branch)
        if not state:
            raise ValueError(f"No flow for branch '{branch}'")

        # Fetch handoff events
        events = self.handoff_service.get_success_handoff_events(branch, limit=limit)

        # Fetch latest verdict
        latest_verdict = self.verdict_service.get_latest_verdict(branch)

        # Fetch live sessions from registry
        live_sessions = self._get_live_sessions_for_branch(branch)

        # Fetch recent updates from handoff file (all entries)
        recent_updates = self.handoff_service.storage.get_recent_updates(
            branch, limit=limit
        )

        # Resolve worktree path for the target branch
        worktree_path = self.git_client.find_worktree_path_for_branch(branch)
        if worktree_path:
            worktree_root = str(worktree_path)
        else:
            # Fallback: if branch has no dedicated worktree, use current
            worktree_root = self.git_client.get_worktree_root()

        return HandoffStatusResult(
            flow_slug=state.flow_slug,
            worktree_root=worktree_root,
            state=state,
            events=events,
            latest_verdict=latest_verdict,
            live_sessions=live_sessions,
            recent_updates=recent_updates,
        )

    def _get_live_sessions_for_branch(self, branch: str) -> list[dict[str, Any]]:
        """Return truly live runtime sessions from the registry for a branch.

        This method instantiates SessionRegistryService with CodeagentBackend
        on-demand to confirm tmux liveness for each session.

        Args:
            branch: Branch name to filter sessions by

        Returns:
            List of session dicts that are truly live
        """

        if self.session_registry is None:
            with self._registry_lock:
                if self.session_registry is None:
                    backend = self._backend
                    self.session_registry = SessionRegistryService(
                        store=self.store, backend=backend
                    )

        return self.session_registry.get_truly_live_sessions_for_branch(branch)
