"""Project status synchronization service.

Synchronizes issue state labels to GitHub Project Status field.
"""

from loguru import logger

from vibe3.clients.github_project_client import GitHubProjectClient
from vibe3.models.orchestration import IssueState


class ProjectStatusSyncService:
    """Service for syncing issue state to GitHub Project status.

    Maps IssueState values to Project Status field values.
    Handles errors gracefully to avoid blocking main flow.
    """

    # Mapping from IssueState to Project Status field values
    STATE_TO_STATUS: dict[IssueState, str] = {
        IssueState.READY: "Ready",
        IssueState.CLAIMED: "Ready",  # Claimed but not started
        IssueState.IN_PROGRESS: "In Progress",
        IssueState.BLOCKED: "Blocked",
        IssueState.HANDOFF: "In Review",  # Waiting for handoff/review
        IssueState.REVIEW: "In Review",
        IssueState.MERGE_READY: "Done",  # Complete, waiting for merge
        IssueState.DONE: "Done",
    }

    def __init__(
        self,
        owner: str,
        project_number: int,
        owner_type: str = "user",
        status_field_name: str = "Status",
    ) -> None:
        """Initialize the sync service.

        Args:
            owner: GitHub user or org name
            project_number: Project number
            owner_type: "user" or "org" (default: "user")
            status_field_name: Name of the Status field in the project
        """
        self.client = GitHubProjectClient(owner, project_number, owner_type)
        self.status_field_name = status_field_name

    def sync_issue_status(self, issue_number: int, state: IssueState) -> bool:
        """Sync issue state to GitHub Project status.

        Args:
            issue_number: GitHub issue number
            state: Issue state to sync

        Returns:
            True if sync succeeded, False otherwise

        Note:
            Failures are logged but don't raise exceptions to avoid
            blocking the main flow.
        """
        try:
            # Find the project item
            item_id = self.client.find_item_by_issue(issue_number)

            if not item_id:
                logger.bind(
                    domain="project_sync",
                    operation="sync_issue_status",
                    issue_number=issue_number,
                ).debug(f"Issue #{issue_number} not found in project, skipping sync")
                return False

            # Map state to status
            status_value = self.STATE_TO_STATUS.get(state)

            if not status_value:
                logger.bind(
                    domain="project_sync",
                    operation="sync_issue_status",
                    issue_number=issue_number,
                    state=state.value,
                ).warning(f"No status mapping for state '{state.value}'")
                return False

            # Update project status
            self.client.update_item_status(
                item_id=item_id,
                status_value=status_value,
                status_field_name=self.status_field_name,
            )

            logger.bind(
                domain="project_sync",
                operation="sync_issue_status",
                issue_number=issue_number,
                state=state.value,
                status=status_value,
            ).info(
                f"Synced issue #{issue_number} state '{state.value}' "
                f"to project status '{status_value}'"
            )

            return True

        except Exception as e:
            logger.bind(
                domain="project_sync",
                operation="sync_issue_status",
                issue_number=issue_number,
                state=state.value,
            ).warning(f"Project status sync failed: {e}")
            return False

    def get_status_for_state(self, state: IssueState) -> str | None:
        """Get the Project Status value for an IssueState.

        Args:
            state: Issue state

        Returns:
            Project Status value or None if not mapped
        """
        return self.STATE_TO_STATUS.get(state)
