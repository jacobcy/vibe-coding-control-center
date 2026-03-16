"""PR service implementation."""

import sys
from pathlib import Path

# Add lib to path for Vibe3Store
lib_path = Path(__file__).parent.parent.parent / "lib"
if str(lib_path) not in sys.path:
    sys.path.insert(0, str(lib_path))


from loguru import logger  # noqa: E402
from store import Vibe3Store  # noqa: E402

from vibe3.clients.git_client import GitClient  # noqa: E402
from vibe3.clients.github_client import GitHubClient, GitHubClientProtocol  # noqa: E402
from vibe3.models.pr import (  # noqa: E402
    CreatePRRequest,
    PRMetadata,
    PRResponse,
    ReviewResponse,
    VersionBumpResponse,
)
from vibe3.services.review_service import ReviewService  # noqa: E402
from vibe3.services.version_service import VersionService  # noqa: E402


class PRService:
    """Service for managing pull requests."""

    def __init__(
        self,
        github_client: GitHubClientProtocol | None = None,
        git_client: GitClient | None = None,
        store: Vibe3Store | None = None,
        version_service: VersionService | None = None,
        review_service: ReviewService | None = None,
    ) -> None:
        """Initialize PR service.

        Args:
            github_client: GitHub client for API operations
            git_client: Git client for repository operations
            store: Vibe3Store instance for persistence
            version_service: Version service for version calculations
            review_service: Review service for PR review
        """
        self.github_client = github_client or GitHubClient()
        self.git_client = git_client or GitClient()
        self.store = store or Vibe3Store()
        self.version_service = version_service or VersionService()
        self.review_service = review_service or ReviewService()

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
        logger.info(
            "Creating draft PR",
            title=title,
            base=base_branch,
            metadata=metadata,
            actor=actor,
        )

        # Check auth
        if not self.github_client.check_auth():
            raise RuntimeError(
                "Not authenticated to GitHub. Run 'gh auth login' first."
            )

        # Get current branch
        head_branch = self.git_client.get_current_branch()

        # Build PR body with metadata
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

        # Update flow state with PR number
        self.store.update_flow_state(
            head_branch,
            pr_number=pr.number,
            latest_actor=actor,
        )

        # Add PR creation event
        self.store.add_event(
            head_branch,
            "pr_created",
            actor,
            f"Draft PR #{pr.number} created: {pr.url}",
        )

        logger.info("Draft PR created", pr_number=pr.number, url=pr.url)
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
        logger.debug("Getting PR", pr_number=pr_number, branch=branch)

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
        logger.info("Marking PR as ready", pr_number=pr_number, actor=actor)

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
            logger.warning("PR is not a draft", pr_number=pr_number)
            return pr

        # Mark as ready
        updated_pr = self.github_client.mark_ready(pr_number)

        # Add event
        branch = pr.head_branch
        self.store.add_event(
            branch,
            "pr_ready",
            actor,
            f"PR #{pr_number} marked as ready for review",
        )

        logger.info("PR marked as ready", pr_number=pr_number)
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
        logger.info("Merging PR", pr_number=pr_number, actor=actor)

        # Check auth
        if not self.github_client.check_auth():
            raise RuntimeError(
                "Not authenticated to GitHub. Run 'gh auth login' first."
            )

        # Get PR first to check state
        pr = self.github_client.get_pr(pr_number)
        if not pr:
            raise RuntimeError(f"PR #{pr_number} not found")

        # Merge PR
        merged_pr = self.github_client.merge_pr(pr_number)

        # Update flow state
        branch = pr.head_branch
        self.store.update_flow_state(
            branch,
            flow_status="merged",
            latest_actor=actor,
        )

        # Add merge event
        self.store.add_event(
            branch,
            "pr_merged",
            actor,
            f"PR #{pr_number} merged",
        )

        logger.info("PR merged", pr_number=pr_number)
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
        logger.info("Calculating version bump", pr_number=pr_number, group=group)

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

    def review_pr(self, pr_number: int, publish: bool = True) -> "ReviewResponse":
        """Review PR using local LLM (codex).

        Args:
            pr_number: PR number
            publish: Whether to publish review as comment

        Returns:
            Review response

        Raises:
            RuntimeError: If PR not found or codex unavailable
        """
        return self.review_service.review_pr(pr_number, publish)
