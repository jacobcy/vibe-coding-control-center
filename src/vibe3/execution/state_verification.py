"""State verification service for noop gate.

Separates external I/O (GitHub API) from business logic (noop gate).
This service handles:
- GitHub API calls to read issue state
- Retry logic with limits
- Error recording to error_log
- Raising appropriate exception types
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NoReturn

from loguru import logger

from vibe3.exceptions import GitHubAPIError

if TYPE_CHECKING:
    from vibe3.clients import SQLiteClient


class StateVerificationService:
    """Pure external dependency: read issue state from GitHub.

    Handles all GitHub API interactions with retry logic.
    Raises RuntimeInfrastructureError on failure (never triggers block_flow).
    """

    MAX_RETRIES = 3

    def __init__(
        self,
        store: SQLiteClient | None = None,
    ) -> None:
        self.store = store

    def get_issue_state_label(
        self,
        issue_number: int,
        repo: str | None = None,
        branch: str | None = None,
        flow_state: dict | None = None,
        tick_id: int = 0,
    ) -> tuple[str | None, bool]:
        """Get current state label and closed status from GitHub issue.

        Args:
            issue_number: Issue number to query
            repo: Repository (defaults to current repo)
            branch: Branch for retry counter persistence
            flow_state: Flow state dict for retry counter
            tick_id: Current heartbeat tick, preserved when retry-limit failures
                are recorded to error_log

        Returns:
            Tuple of (state_label, is_closed) where:
            - state_label: State label string (e.g., "state/in-progress") or None
            - is_closed: True if issue state is "CLOSED", False otherwise

        Raises:
            GitHubAPIError: If GitHub API fails after max retries
        """
        from vibe3.clients.github_client import GitHubClient

        try:
            issue_payload = GitHubClient().view_issue(issue_number, repo=repo)
        except Exception as exc:
            self._handle_github_api_failure(
                exc, issue_number, branch, flow_state, tick_id
            )

        if not isinstance(issue_payload, dict):
            self._handle_malformed_response(
                issue_payload, issue_number, branch, flow_state, tick_id
            )

        # Extract is_closed from the issue payload
        is_closed = str(issue_payload.get("state", "")).upper() == "CLOSED"

        labels = issue_payload.get("labels", [])
        if not isinstance(labels, list):
            self._handle_malformed_response(
                issue_payload, issue_number, branch, flow_state, tick_id
            )

        for label in labels:
            if isinstance(label, dict):
                label_name = label.get("name", "")
                if not isinstance(label_name, str):
                    continue
            else:
                label_name = str(label)
            if label_name.startswith("state/"):
                return label_name, is_closed

        return None, is_closed

    def _handle_github_api_failure(
        self,
        exc: Exception,
        issue_number: int,
        branch: str | None,
        flow_state: dict | None,
        tick_id: int,
    ) -> NoReturn:
        retry_count = (
            flow_state.get("noop_gate_github_retry_count", 0) if flow_state else 0
        )

        if retry_count >= self.MAX_RETRIES:
            self._record_api_error(
                issue_number,
                branch,
                f"GitHub API failed after {retry_count} retries: {exc}",
                retry_count,
                tick_id,
            )
            raise GitHubAPIError(
                f"Cannot verify remote state for #{issue_number} "
                f"after {retry_count} retries: {exc}"
            ) from exc

        self._increment_retry_counter(
            branch, flow_state, "noop_gate_github_retry_count", retry_count
        )
        logger.bind(
            domain="state_verification",
            issue_number=issue_number,
            branch=branch,
        ).warning(f"GitHub API RETRY ({retry_count + 1}/{self.MAX_RETRIES}): {exc}")
        raise GitHubAPIError(
            f"Cannot verify remote state for #{issue_number}: {exc}"
        ) from exc

    def _handle_malformed_response(
        self,
        response: object,
        issue_number: int,
        branch: str | None,
        flow_state: dict | None,
        tick_id: int,
    ) -> NoReturn:
        retry_count = (
            flow_state.get("noop_gate_malformed_retry_count", 0) if flow_state else 0
        )

        if retry_count >= self.MAX_RETRIES:
            self._record_api_error(
                issue_number,
                branch,
                f"Malformed GitHub response after {retry_count} retries",
                retry_count,
                tick_id,
            )
            raise GitHubAPIError(
                f"Malformed GitHub response for #{issue_number} "
                f"after {retry_count} retries"
            )

        self._increment_retry_counter(
            branch, flow_state, "noop_gate_malformed_retry_count", retry_count
        )
        logger.bind(
            domain="state_verification",
            issue_number=issue_number,
            branch=branch,
        ).warning(f"Malformed response RETRY ({retry_count + 1}/{self.MAX_RETRIES})")
        raise GitHubAPIError(f"Malformed GitHub response for #{issue_number}")

    def _increment_retry_counter(
        self,
        branch: str | None,
        flow_state: dict | None,
        counter_key: str,
        current_count: int,
    ) -> None:
        """Increment and persist retry counter."""
        if flow_state is not None:
            flow_state[counter_key] = current_count + 1
            if self.store and branch:
                self.store.update_flow_state(branch, **{counter_key: current_count + 1})

    def _record_api_error(
        self,
        issue_number: int,
        branch: str | None,
        error_message: str,
        retry_count: int,
        tick_id: int,
    ) -> None:
        """Record API error to error_log."""
        if not self.store:
            return

        try:
            from vibe3.services.shared.errors import record_error

            record_error(
                error_code="E_API_UNAVAILABLE",
                error_message=error_message,
                tick_id=tick_id,
                issue_number=issue_number,
                branch=branch,
                store=self.store,
            )
        except Exception as record_exc:
            logger.bind(
                domain="state_verification",
                issue_number=issue_number,
                branch=branch,
            ).warning(f"Failed to record error to error_log: {record_exc}")
