"""PR service implementation."""

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.protocols import GitHubClientProtocol
from vibe3.exceptions import GitError, UserError
from vibe3.models.pr import (
    CreatePRRequest,
    PRResponse,
    VersionBumpResponse,
)
from vibe3.services.pr_review_briefing_service import PRReviewBriefingService
from vibe3.services.pr_utils import (
    build_pr_body,
    check_upstream_conflicts,
    get_metadata_from_flow,
)
from vibe3.services.signature_service import SignatureService
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
        """Initialize PR service."""
        self.github_client = GitHubClient() if github_client is None else github_client
        self.git_client = GitClient() if git_client is None else git_client
        self.store = SQLiteClient() if store is None else store
        self.version_service = (
            VersionService() if version_service is None else version_service
        )
        self.briefing_service = PRReviewBriefingService(self.github_client)

    def create_draft_pr(
        self,
        title: str,
        body: str,
        base_branch: str = "main",
        actor: str | None = None,
    ) -> PRResponse:
        """Create a draft PR."""
        logger.bind(
            domain="pr",
            action="create_draft",
            title=title,
            base_branch=base_branch,
            actor=actor,
        ).info("Creating draft PR")

        if not self.github_client.check_auth():
            raise RuntimeError(
                "Not authenticated to GitHub. Run 'gh auth login' first."
            )

        check_upstream_conflicts(
            self.git_client,
            "create",
            base_branch=base_branch,
        )

        head_branch = self.git_client.get_current_branch()
        effective_actor = SignatureService.resolve_for_branch(
            self.store,
            head_branch,
            explicit_actor=actor,
        )

        existing_prs = self.github_client.list_prs_for_branch(head_branch)
        if existing_prs:
            existing = existing_prs[0]
            hydrated = self.github_client.get_pr(existing.number) or existing
            self._sync_pr_flow_state(hydrated, actor=effective_actor)
            return hydrated

        try:
            self.git_client.push_branch(head_branch, set_upstream=True)
        except GitError as exc:
            raise UserError(
                f"Failed to push branch '{head_branch}' before PR creation: {exc}\n"
                f"Tips:\n"
                f"  1. Run 'git branch -vv' and check whether '{head_branch}' is "
                f"incorrectly tracking origin/main\n"
                f"  2. Resolve local/remote divergence or upstream misconfiguration\n"
                f"  3. Ensure you have push permission to origin\n"
                f"  4. If automation is still blocked, use 'gh pr create' manually "
                f"after fixing the branch/upstream state"
            ) from exc

        metadata = get_metadata_from_flow(self.store, head_branch)
        enhanced_body = build_pr_body(body, metadata)
        request = CreatePRRequest(
            title=title,
            body=enhanced_body,
            head_branch=head_branch,
            base_branch=base_branch,
            draft=True,
            metadata=metadata,
        )

        pr = self.github_client.create_pr(request)

        self._sync_pr_flow_state(pr, actor=effective_actor)
        self.store.add_event(
            head_branch,
            "pr_draft",
            effective_actor,
            f"Draft PR #{pr.number} created: {pr.url}",
        )

        logger.bind(pr_number=pr.number, url=pr.url).success("Draft PR created")
        return pr

    def get_pr(
        self, pr_number: int | None = None, branch: str | None = None
    ) -> PRResponse | None:
        """Get PR details."""
        logger.bind(
            domain="pr", action="get", pr_number=pr_number, branch=branch
        ).debug("Getting PR")

        if branch is None and pr_number is None:
            branch = self.git_client.get_current_branch()

        pr = self.github_client.get_pr(pr_number, branch)
        if pr:
            pr.comments = self.github_client.list_pr_comments(pr.number)
            pr.review_comments = self.github_client.list_pr_review_comments(pr.number)
        return pr

    def mark_ready(
        self,
        pr_number: int,
        actor: str | None = None,
        requested_reviewers: list[str] | None = None,
    ) -> PRResponse:
        """Mark PR as ready for review with optional AI review request."""
        logger.bind(
            domain="pr",
            action="mark_ready",
            pr_number=pr_number,
            actor=actor,
            requested_reviewers=requested_reviewers,
        ).info("Marking PR as ready")

        if not self.github_client.check_auth():
            raise RuntimeError(
                "Not authenticated to GitHub. Run 'gh auth login' first."
            )

        pr = self.github_client.get_pr(pr_number)
        if not pr:
            raise RuntimeError(f"PR #{pr_number} not found")
        effective_actor = SignatureService.resolve_for_branch(
            self.store,
            pr.head_branch,
            explicit_actor=actor,
        )

        check_upstream_conflicts(
            self.git_client,
            "ready",
            base_branch=pr.base_branch,
        )

        if not pr.draft:
            self._sync_pr_flow_state(pr, actor=effective_actor)
            try:
                self.briefing_service.publish_briefing(
                    pr_number, requested_reviewers=requested_reviewers
                )
            except Exception as e:
                logger.bind(pr_number=pr_number).warning(
                    f"Briefing update failed (PR still ready): {e}"
                )
            # Request AI review if specified
            if requested_reviewers:
                try:
                    self.github_client.request_ai_review(pr_number, requested_reviewers)
                except Exception as e:
                    logger.bind(pr_number=pr_number).warning(
                        f"Review request failed (PR still ready): {e}"
                    )
            logger.bind(pr_number=pr_number).info("PR already ready; confirmed")
            return pr

        updated_pr = self.github_client.mark_ready(pr_number)
        branch = pr.head_branch
        self._sync_pr_flow_state(updated_pr, actor=effective_actor)

        try:
            self.briefing_service.publish_briefing(
                pr_number, requested_reviewers=requested_reviewers
            )
        except Exception as e:
            logger.bind(pr_number=pr_number).warning(
                f"Briefing publication failed (PR marked ready): {e}"
            )

        # Request AI review if specified
        if requested_reviewers:
            try:
                self.github_client.request_ai_review(pr_number, requested_reviewers)
            except Exception as e:
                logger.bind(pr_number=pr_number).warning(
                    f"Review request failed (PR marked ready): {e}"
                )

        self.store.add_event(
            branch,
            "pr_ready",
            effective_actor,
            f"PR #{pr_number} marked as ready for review",
        )

        logger.bind(pr_number=pr_number).success("PR marked as ready")
        return updated_pr

    def sync_pr_state_from_remote(
        self, pr: PRResponse, actor: str | None = None
    ) -> None:
        """Synchronize local flow PR fields from remote PR fact."""
        effective_actor = SignatureService.resolve_for_branch(
            self.store,
            pr.head_branch,
            explicit_actor=actor,
        )
        self._sync_pr_flow_state(pr, actor=effective_actor)

    def merge_pr(self, pr_number: int, actor: str | None = None) -> PRResponse:
        """Merge PR."""
        logger.bind(domain="pr", action="merge", pr_number=pr_number, actor=actor).info(
            "Merging PR"
        )

        if not self.github_client.check_auth():
            raise RuntimeError(
                "Not authenticated to GitHub. Run 'gh auth login' first."
            )

        pr = self.github_client.get_pr(pr_number)
        if not pr:
            raise RuntimeError(f"PR #{pr_number} not found")
        effective_actor = SignatureService.resolve_for_branch(
            self.store,
            pr.head_branch,
            explicit_actor=actor,
        )

        merged_pr = self.github_client.merge_pr(pr_number)

        branch = pr.head_branch
        self.store.update_flow_state(
            branch,
            flow_status="done",
            latest_actor=effective_actor,
        )
        self.store.add_event(
            branch,
            "pr_merge",
            effective_actor,
            f"PR #{pr_number} merged",
        )

        logger.bind(pr_number=pr_number).success("PR merged")
        return merged_pr

    def calculate_version_bump(
        self, pr_number: int, group: str | None = None
    ) -> VersionBumpResponse:
        """Calculate version bump for PR."""
        logger.bind(
            domain="pr",
            action="calculate_version_bump",
            pr_number=pr_number,
            group=group,
        ).info("Calculating version bump")

        pr = self.github_client.get_pr(pr_number)
        if not pr:
            raise RuntimeError(f"PR #{pr_number} not found")
        return self.version_service.calculate_bump(group)

    def close_pr(self, pr_number: int, comment: str | None = None) -> bool:
        """Close a pull request.

        Args:
            pr_number: PR number to close
            comment: Optional comment to add before closing

        Returns:
            True if PR was closed successfully
        """
        logger.bind(
            domain="pr",
            action="close",
            pr_number=pr_number,
        ).info("Closing PR")

        if not self.github_client.check_auth():
            raise RuntimeError(
                "Not authenticated to GitHub. Run 'gh auth login' first."
            )

        return self.github_client.close_pr(pr_number, comment=comment)

    def close_open_pr_for_flow(
        self, branch: str, comment: str | None = None
    ) -> int | None:
        """Close open PR for a flow branch if one exists.

        Args:
            branch: Branch name to check for open PR
            comment: Optional comment to add before closing

        Returns:
            PR number if a PR was closed, None otherwise
        """
        logger.bind(
            domain="pr",
            action="close_open_pr_for_flow",
            branch=branch,
        ).info("Checking for open PR to close")

        prs = self.github_client.list_prs_for_branch(branch, state="open")
        if not prs:
            logger.bind(branch=branch).info("No open PR found for branch")
            return None

        pr = prs[0]
        success = self.close_pr(pr.number, comment=comment)

        if success:
            logger.bind(
                branch=branch,
                pr_number=pr.number,
            ).success("Closed open PR for branch")
            return pr.number
        else:
            logger.bind(
                branch=branch,
                pr_number=pr.number,
            ).warning("Failed to close PR (close_pr returned False)")
            return None

    def _sync_pr_flow_state(self, pr: PRResponse, actor: str) -> None:
        """Persist activity to flow and update PR context cache."""
        self.store.update_flow_state(
            pr.head_branch,
            latest_actor=actor,
            pr_ref=pr.url,  # Write PR URL as proof of PR creation
        )

        # Update PR context cache with latest PR info
        # Get existing cache or create new entry
        existing_cache = self.store.get_flow_context_cache(pr.head_branch)

        self.store.upsert_flow_context_cache(
            branch=pr.head_branch,
            task_issue_number=(
                existing_cache.get("task_issue_number") if existing_cache else None
            ),
            issue_title=existing_cache.get("issue_title") if existing_cache else None,
            pr_number=pr.number,
            pr_title=pr.title,
        )
