"""PR service implementation."""

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.protocols import GitHubClientProtocol
from vibe3.models.pr import (
    CreatePRRequest,
    PRMetadata,
    PRResponse,
    VersionBumpResponse,
)
from vibe3.services.version_service import VersionService


class PRService:
    """Service for managing pull requests."""

    def __init__(
        self,
        github_client: GitHubClientProtocol | None = None,
        git_client: GitClient | None = None,
        store: SQLiteClient | None = None,
        version_service: VersionService | None = None,
    ) -> None:
        """Initialize PR service.

        Args:
            github_client: GitHub client for API operations
            git_client: Git client for repository operations
            store: SQLiteClient instance for persistence
            version_service: Version service for version calculations
        """
        self.github_client = github_client or GitHubClient()
        self.git_client = git_client or GitClient()
        self.store = store or SQLiteClient()
        self.version_service = version_service or VersionService()

    def create_draft_pr(
        self,
        title: str,
        body: str,
        base_branch: str = "main",
        metadata: PRMetadata | None = None,
        actor: str = "unknown",
    ) -> PRResponse:
        """Create a draft PR.

        Args:
            title: PR title
            body: PR body/description
            base_branch: Base branch name
            metadata: PR metadata (task, flow, spec, etc.)
            actor: Actor creating the PR

        Returns:
            Created PR response

        Raises:
            RuntimeError: If PR creation fails
        """
        logger.bind(
            domain="pr",
            action="create_draft",
            title=title,
            base_branch=base_branch,
            metadata=metadata,
            actor=actor,
        ).info("Creating draft PR")

        # Check auth
        if not self.github_client.check_auth():
            raise RuntimeError(
                "Not authenticated to GitHub. Run 'gh auth login' first."
            )

        # Get current branch and build PR body
        head_branch = self.git_client.get_current_branch()
        enhanced_body = self._build_pr_body(body, metadata)

        # Create PR
        request = CreatePRRequest(
            title=title,
            body=enhanced_body,
            head_branch=head_branch,
            base_branch=base_branch,
            draft=True,
            metadata=metadata,
        )

        pr = self.github_client.create_pr(request)

        # Update flow state and add event
        self.store.update_flow_state(
            head_branch, pr_number=pr.number, latest_actor=actor
        )
        self.store.add_event(
            head_branch, "pr_draft", actor, f"Draft PR #{pr.number} created: {pr.url}"
        )

        logger.bind(pr_number=pr.number, url=pr.url).success("Draft PR created")
        return pr

    def get_pr(
        self, pr_number: int | None = None, branch: str | None = None
    ) -> PRResponse | None:
        """Get PR details.

        Args:
            pr_number: PR number
            branch: Branch name

        Returns:
            PR response or None if not found
        """
        logger.bind(
            domain="pr", action="get", pr_number=pr_number, branch=branch
        ).debug("Getting PR")

        if branch is None and pr_number is None:
            branch = self.git_client.get_current_branch()

        return self.github_client.get_pr(pr_number, branch)

    def mark_ready(self, pr_number: int, actor: str = "unknown") -> PRResponse:
        """Mark PR as ready for review.

        Args:
            pr_number: PR number
            actor: Actor marking PR as ready

        Returns:
            Updated PR response

        Raises:
            RuntimeError: If operation fails
        """
        logger.bind(
            domain="pr", action="mark_ready", pr_number=pr_number, actor=actor
        ).info("Marking PR as ready")

        # Check auth
        if not self.github_client.check_auth():
            raise RuntimeError(
                "Not authenticated to GitHub. Run 'gh auth login' first."
            )

        # Get PR first to check state
        pr = self.github_client.get_pr(pr_number)
        if not pr:
            raise RuntimeError(f"PR #{pr_number} not found")

        if not pr.draft:
            logger.bind(pr_number=pr_number).warning("PR is not a draft")
            return pr

        # Mark as ready
        updated_pr = self.github_client.mark_ready(pr_number)

        # Add event
        branch = pr.head_branch
        self.store.add_event(
            branch, "pr_ready", actor, f"PR #{pr_number} marked as ready for review"
        )

        logger.bind(pr_number=pr_number).success("PR marked as ready")
        return updated_pr

    def merge_pr(self, pr_number: int, actor: str = "unknown") -> PRResponse:
        """Merge PR.

        Args:
            pr_number: PR number
            actor: Actor merging the PR

        Returns:
            Merged PR response

        Raises:
            RuntimeError: If merge fails
        """
        logger.bind(domain="pr", action="merge", pr_number=pr_number, actor=actor).info(
            "Merging PR"
        )

        # Check auth
        if not self.github_client.check_auth():
            raise RuntimeError(
                "Not authenticated to GitHub. Run 'gh auth login' first."
            )

        # Get PR first to check state
        pr = self.github_client.get_pr(pr_number)
        if not pr:
            raise RuntimeError(f"PR #{pr_number} not found")

        # Merge PR and update flow state
        merged_pr = self.github_client.merge_pr(pr_number)

        branch = pr.head_branch
        self.store.update_flow_state(
            branch,
            flow_status="done",
            latest_actor=actor,
        )
        self.store.add_event(
            branch,
            "pr_merge",
            actor,
            f"PR #{pr_number} merged",
        )

        logger.bind(pr_number=pr_number).success("PR merged")
        return merged_pr

    def calculate_version_bump(
        self,
        pr_number: int,
        group: str | None = None,
    ) -> VersionBumpResponse:
        """Calculate version bump for PR.

        Args:
            pr_number: PR number
            group: Task group (feature/bug/docs/chore)

        Returns:
            Version bump response

        Raises:
            RuntimeError: If PR not found
        """
        logger.bind(
            domain="pr",
            action="calculate_version_bump",
            pr_number=pr_number,
            group=group,
        ).info("Calculating version bump")

        # Get PR to verify it exists
        pr = self.github_client.get_pr(pr_number)
        if not pr:
            raise RuntimeError(f"PR #{pr_number} not found")

        # Use version service for calculation (reads from VERSION file)
        return self.version_service.calculate_bump(group)

    def _build_pr_body(self, body: str, metadata: PRMetadata | None = None) -> str:
        """Build PR body with metadata.

        Args:
            body: Original PR body
            metadata: PR metadata

        Returns:
            Enhanced PR body with metadata section
        """
        if not metadata:
            return body

        metadata_section = "\n\n---\n\n## Vibe3 Metadata\n\n"

        if metadata.task_issue:
            metadata_section += f"**Task Issue:** #{metadata.task_issue}\n"
        if metadata.flow_slug:
            metadata_section += f"**Flow:** {metadata.flow_slug}\n"
        if metadata.spec_ref:
            metadata_section += f"**Spec Ref:** {metadata.spec_ref}\n"
        if metadata.planner:
            metadata_section += f"**Planner:** {metadata.planner}\n"
        if metadata.executor:
            metadata_section += f"**Executor:** {metadata.executor}\n"

        return body + metadata_section
