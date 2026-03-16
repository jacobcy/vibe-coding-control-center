"""PR service implementation."""
import sys
from pathlib import Path

# Add lib to path for Vibe3Store
lib_path = Path(__file__).parent.parent.parent / "lib"
if str(lib_path) not in sys.path:
    sys.path.insert(0, str(lib_path))

from typing import Literal

from loguru import logger

from vibe3.clients.github_client import GitHubClient, GitHubClientProtocol
from vibe3.clients.git_client import GitClient
from vibe3.models.pr import (
    CreatePRRequest,
    PRMetadata,
    PRResponse,
    UpdatePRRequest,
    VersionBumpRequest,
    VersionBumpResponse,
    VersionBumpType,
)
from store import Vibe3Store


class PRService:
    """Service for managing pull requests."""

    def __init__(
        self,
        github_client: GitHubClientProtocol | None = None,
        git_client: GitClient | None = None,
        store: Vibe3Store | None = None,
    ) -> None:
        """Initialize PR service.

        Args:
            github_client: GitHub client for API operations
            git_client: Git client for repository operations
            store: Vibe3Store instance for persistence
        """
        self.github_client = github_client or GitHubClient()
        self.git_client = git_client or GitClient()
        self.store = store or Vibe3Store()

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
            raise RuntimeError("Not authenticated to GitHub. Run 'gh auth login' first.")

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

    def get_pr(self, pr_number: int | None = None, branch: str | None = None) -> PRResponse | None:
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
            raise RuntimeError("Not authenticated to GitHub. Run 'gh auth login' first.")

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
            raise RuntimeError("Not authenticated to GitHub. Run 'gh auth login' first.")

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
        """
        logger.info("Calculating version bump", pr_number=pr_number, group=group)

        # Get PR
        pr = self.github_client.get_pr(pr_number)
        if not pr:
            raise RuntimeError(f"PR #{pr_number} not found")

        # Determine bump type based on group
        # TODO: Implement actual version calculation logic
        # For now, use simple rules from the plan:
        # - feature: minor version
        # - bug: patch version
        # - docs/chore: no bump (unless explicit --bump)

        if group == "feature":
            bump_type = VersionBumpType.MINOR
            reason = "Feature tasks trigger minor version bump"
        elif group == "bug":
            bump_type = VersionBumpType.PATCH
            reason = "Bug fixes trigger patch version bump"
        elif group in ("docs", "chore"):
            bump_type = VersionBumpType.NONE
            reason = "Docs/chore tasks do not trigger version bump by default"
        else:
            # Default to patch for unknown groups
            bump_type = VersionBumpType.PATCH
            reason = "Default to patch version bump"

        # TODO: Get current version from version file or package.json
        current_version = "0.1.0"
        next_version = self._calculate_next_version(current_version, bump_type)

        return VersionBumpResponse(
            current_version=current_version,
            bump_type=bump_type,
            next_version=next_version,
            reason=reason,
        )

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

    def _calculate_next_version(self, current: str, bump_type: VersionBumpType) -> str:
        """Calculate next version based on bump type.

        Args:
            current: Current version (semver)
            bump_type: Version bump type

        Returns:
            Next version
        """
        if bump_type == VersionBumpType.NONE:
            return current

        parts = current.split(".")
        if len(parts) != 3:
            raise ValueError(f"Invalid version format: {current}")

        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

        if bump_type == VersionBumpType.MAJOR:
            major += 1
            minor = 0
            patch = 0
        elif bump_type == VersionBumpType.MINOR:
            minor += 1
            patch = 0
        elif bump_type == VersionBumpType.PATCH:
            patch += 1

        return f"{major}.{minor}.{patch}"