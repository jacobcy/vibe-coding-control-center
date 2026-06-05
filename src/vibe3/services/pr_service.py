"""PR service implementation."""

import time
from datetime import datetime
from pathlib import Path
from typing import cast

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.protocols import GitHubClientProtocol
from vibe3.clients.recent_pr_cache import RecentPRCache
from vibe3.exceptions import GitError, PRNotFoundError, UserError
from vibe3.models.pr import (
    CreatePRRequest,
    PRResponse,
    PRState,
    VersionBumpResponse,
)
from vibe3.services.pr_loc_comment_service import PRLocCommentService
from vibe3.services.pr_review_briefing_service import PRReviewBriefingService
from vibe3.services.shared.pr_utils import (
    build_pr_body,
    check_upstream_conflicts,
    get_metadata_from_flow,
)
from vibe3.services.shared.signatures import SignatureService
from vibe3.services.version_service import VersionService


def _format_datetime_iso(dt: datetime | None) -> str | None:
    """Format datetime to ISO string, pass through None and str."""
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    return dt.isoformat()


class PRService:
    """Service for managing pull requests."""

    def __init__(
        self,
        github_client: GitHubClientProtocol | None = None,
        git_client: GitClient | None = None,
        store: SQLiteClient | None = None,
        version_service: VersionService | None = None,
        loc_comment_service: PRLocCommentService | None = None,
    ) -> None:
        """Initialize PR service."""
        self.github_client: GitHubClientProtocol = (
            cast(GitHubClientProtocol, GitHubClient())
            if github_client is None
            else github_client
        )
        self.git_client = GitClient() if git_client is None else git_client
        self.store = SQLiteClient() if store is None else store
        self.version_service = (
            VersionService() if version_service is None else version_service
        )
        self.briefing_service = PRReviewBriefingService(self.github_client)
        self.loc_comment_service = loc_comment_service or PRLocCommentService(
            self.github_client
        )
        self._recent_pr_cache_map: dict[str, PRResponse] = {}
        self._recent_pr_cache_client: RecentPRCache | None = None
        self._pr_cache: dict[int, tuple[PRResponse, float]] = {}
        self._pr_cache_ttl: float = 60.0

    @property
    def recent_pr_cache(self) -> RecentPRCache:
        """Persistent recent PR cache rooted at the repository common dir."""
        if self._recent_pr_cache_client is None:
            try:
                git_common_dir = self.git_client.get_git_common_dir()
                repo_path = (
                    Path(git_common_dir).parent if git_common_dir else Path.cwd()
                )
            except Exception:
                repo_path = Path.cwd()
            self._recent_pr_cache_client = RecentPRCache(repo_path)
        return self._recent_pr_cache_client

    def _cache_entry_to_pr(
        self, branch: str, data: dict[str, object]
    ) -> PRResponse | None:
        """Convert cached JSON data back to PRResponse."""
        try:
            merged_at_raw = data.get("merged_at")
            closed_at_raw = data.get("closed_at")
            number_raw = data.get("number")
            if not isinstance(number_raw, int | str):
                return None
            merged_at = (
                datetime.fromisoformat(merged_at_raw)
                if isinstance(merged_at_raw, str) and merged_at_raw
                else None
            )
            closed_at = (
                datetime.fromisoformat(closed_at_raw)
                if isinstance(closed_at_raw, str) and closed_at_raw
                else None
            )
            state_value = str(data.get("state") or PRState.CLOSED.value)
            return PRResponse(
                number=int(number_raw),
                title=str(data.get("title") or ""),
                body="",
                state=PRState(state_value),
                head_branch=str(data.get("head_branch") or branch),
                base_branch=str(data.get("base_branch") or "main"),
                url=str(data.get("url") or ""),
                draft=bool(data.get("draft", False)),
                is_ready=not bool(data.get("draft", False)),
                ci_passed=False,
                ci_status=None,
                created_at=None,
                updated_at=None,
                merged_at=merged_at,
                closed_at=closed_at,
                metadata=None,
            )
        except (KeyError, ValueError, TypeError):
            return None

    def _sync_branch_context_cache(self, prs: dict[str, PRResponse]) -> None:
        """Project recent PR facts into flow_context_cache."""
        from vibe3.services.issue_title_cache_service import IssueTitleCacheService

        title_cache = IssueTitleCacheService(self.store)
        pr_entries = [(pr.head_branch, pr.number, pr.title) for pr in prs.values()]
        title_cache.update_prs_bulk(pr_entries)

    def refresh_recent_pr_cache(
        self,
        *,
        force: bool = False,
        limit: int = 50,
        max_age_minutes: int = 10,
        sync_context_cache: bool = True,
    ) -> dict[str, PRResponse]:
        """Refresh recent PR cache if stale and return branch -> PR mapping."""
        if force or not self.recent_pr_cache.is_fresh(max_age_minutes=max_age_minutes):
            self.recent_pr_cache.sync(self.github_client, limit=limit)

        cached = self.recent_pr_cache.get_all_branch_prs()
        branch_to_pr: dict[str, PRResponse] = {}
        for branch, data in cached.items():
            if not isinstance(data, dict):
                continue
            pr = self._cache_entry_to_pr(branch, data)
            if pr is not None:
                branch_to_pr[branch] = pr

        self._recent_pr_cache_map = branch_to_pr
        if sync_context_cache:
            # Always sync to ensure flow_context_cache has latest PR info
            # (flow_context_cache may be empty on first access even when recent
            # PR cache is fresh)
            self._sync_branch_context_cache(branch_to_pr)
        return branch_to_pr

    def refresh_open_pr_cache(
        self,
        *,
        force: bool = False,
        limit: int = 50,
        max_age_minutes: int = 10,
        sync_context_cache: bool = True,
    ) -> dict[str, PRResponse]:
        """Return open/draft PRs after ensuring recent PR cache is fresh."""
        recent = self.refresh_recent_pr_cache(
            force=force,
            limit=limit,
            max_age_minutes=max_age_minutes,
            sync_context_cache=sync_context_cache,
        )
        return {branch: pr for branch, pr in recent.items() if pr.state == PRState.OPEN}

    def get_branch_pr_status(
        self,
        branch: str,
        *,
        refresh: bool = True,
        max_age_minutes: int = 10,
        limit: int = 50,
        repo: str | None = None,
        sync_context_cache: bool = True,
    ) -> PRResponse | None:
        """Return branch PR status from recent cache with fallback on miss.

        Bypasses cache when repo is provided to avoid wrong-repo hits.
        """
        # Cross-repo queries bypass cache entirely to avoid wrong-repo hits
        if repo is None:
            cache = (
                self.refresh_recent_pr_cache(
                    force=False,
                    limit=limit,
                    max_age_minutes=max_age_minutes,
                    sync_context_cache=sync_context_cache,
                )
                if refresh
                else self._recent_pr_cache_map
            )
            pr = cache.get(branch)
            if pr is not None:
                return pr

        try:
            prs = self.github_client.list_prs_for_branch(branch, state="all", repo=repo)
        except Exception:
            return None
        if not prs:
            return None

        pr = prs[0]
        # Only update local cache when querying the current repo (no repo override)
        # to avoid polluting cache with PRs from other repositories
        if repo is None:
            self.recent_pr_cache.upsert_branch_pr(
                branch,
                {
                    "number": pr.number,
                    "title": pr.title,
                    "state": pr.state.value,
                    "draft": pr.draft,
                    "url": pr.url,
                    "head_branch": pr.head_branch,
                    "base_branch": pr.base_branch,
                    "merged_at": _format_datetime_iso(pr.merged_at),
                    "closed_at": _format_datetime_iso(pr.closed_at),
                },
            )
            self._recent_pr_cache_map[branch] = pr
            if sync_context_cache:
                self._sync_branch_context_cache({branch: pr})
        return pr

    def get_open_pr_for_branch(
        self,
        branch: str,
        *,
        refresh: bool = True,
    ) -> PRResponse | None:
        """Return the current open/draft PR for a branch, if any."""
        pr = self.get_branch_pr_status(branch, refresh=refresh)
        if pr is not None and pr.state == PRState.OPEN:
            return pr
        return None

    def create_pr(
        self,
        title: str,
        body: str,
        base_branch: str = "main",
        actor: str | None = None,
    ) -> PRResponse:
        """Create a pull request."""
        logger.bind(
            domain="pr",
            action="create",
            title=title,
            base_branch=base_branch,
            actor=actor,
        ).info("Creating pull request")

        if not self.github_client.check_auth():
            raise UserError("Not authenticated to GitHub. Run 'gh auth login' first.")

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

        existing = self.get_open_pr_for_branch(head_branch)
        if existing:
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
            draft=False,
            metadata=metadata,
        )

        pr = self.github_client.create_pr(request)

        self._sync_pr_flow_state(pr, actor=effective_actor)
        self.store.add_event(
            head_branch,
            "pr_created",
            effective_actor,
            f"Pull request #{pr.number} created: {pr.url}",
        )

        logger.bind(pr_number=pr.number, url=pr.url).success("Pull request created")
        return pr

    def get_pr(
        self,
        pr_number: int | None = None,
        branch: str | None = None,
    ) -> PRResponse | None:
        """Get PR details."""
        logger.bind(
            domain="pr", action="get", pr_number=pr_number, branch=branch
        ).debug("Getting PR")

        if pr_number is not None:
            cached = self._pr_cache.get(pr_number)
            if cached and (time.monotonic() - cached[1]) < self._pr_cache_ttl:
                return cached[0]

        if branch is None and pr_number is None:
            branch = self.git_client.get_current_branch()

        pr = self.github_client.get_pr(pr_number, branch)
        if pr:
            pr.comments = self.github_client.list_pr_comments(pr.number)
            pr.review_comments = self.github_client.list_pr_review_comments(pr.number)
            pr.reviews = self.github_client.list_pr_reviews(pr.number)
            if pr_number is not None:
                self._pr_cache[pr_number] = (pr, time.monotonic())
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
            raise UserError("Not authenticated to GitHub. Run 'gh auth login' first.")

        pr = self.github_client.get_pr(pr_number)
        if not pr:
            raise PRNotFoundError(pr_number)
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
            self._finalize_pr_ready(
                pr_number,
                effective_actor,
                requested_reviewers,
                pr_for_sync=pr,
                is_already_ready=True,
            )
            return pr

        updated_pr = self.github_client.mark_ready(pr_number)
        self._finalize_pr_ready(
            pr_number,
            effective_actor,
            requested_reviewers,
            pr_for_sync=updated_pr,
            is_already_ready=False,
        )
        return updated_pr

    def _finalize_pr_ready(
        self,
        pr_number: int,
        actor: str,
        requested_reviewers: list[str] | None = None,
        *,
        pr_for_sync: PRResponse,
        is_already_ready: bool = False,
    ) -> None:
        """Finalize PR ready state: sync, briefing, and AI reviews."""
        self._sync_pr_flow_state(pr_for_sync, actor=actor)

        try:
            self.briefing_service.publish_briefing(
                pr_number, requested_reviewers=requested_reviewers
            )
        except Exception as e:
            action = "update" if is_already_ready else "publication"
            logger.bind(pr_number=pr_number).warning(
                f"Briefing {action} failed (PR ready): {e}"
            )

        # Publish LOC summary comment
        try:
            if self.loc_comment_service:
                self.loc_comment_service.publish_loc_summary(pr_number)
        except Exception as e:
            logger.bind(pr_number=pr_number).warning(
                f"LOC summary publication failed (PR ready): {e}"
            )

        # Request AI review if specified
        if requested_reviewers:
            try:
                self.github_client.request_ai_review(pr_number, requested_reviewers)
            except Exception as e:
                logger.bind(pr_number=pr_number).warning(
                    f"AI review request failed (PR ready): {e}"
                )

        if is_already_ready:
            logger.bind(pr_number=pr_number).info("PR already ready; confirmed")
        else:
            self.store.add_event(
                pr_for_sync.head_branch,
                "pr_ready",
                actor,
                f"PR #{pr_number} marked as ready for review",
            )
            logger.bind(pr_number=pr_number).success("PR marked as ready")

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
            raise UserError("Not authenticated to GitHub. Run 'gh auth login' first.")

        pr = self.github_client.get_pr(pr_number)
        if not pr:
            raise PRNotFoundError(pr_number)
        effective_actor = SignatureService.resolve_for_branch(
            self.store,
            pr.head_branch,
            explicit_actor=actor,
        )

        merged_pr = self.github_client.merge_pr(pr_number)

        branch = pr.head_branch
        # Auto-save baseline snapshot on PR merge
        try:
            from vibe3.analysis import snapshot_service

            snapshot_service.save_branch_baseline(branch)
        except Exception as e:
            logger.warning(f"Failed to save branch baseline on merge: {e}")

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
            raise PRNotFoundError(pr_number)
        return self.version_service.calculate_bump(group)

    def close_pr(self, pr_number: int, comment: str | None = None) -> bool:
        """Close a pull request with optional comment.

        Returns True if PR was closed successfully.
        """
        logger.bind(
            domain="pr",
            action="close",
            pr_number=pr_number,
        ).info("Closing PR")

        if not self.github_client.check_auth():
            raise UserError("Not authenticated to GitHub. Run 'gh auth login' first.")

        return self.github_client.close_pr(pr_number, comment=comment)

    def close_open_pr_for_flow(
        self, branch: str, comment: str | None = None
    ) -> int | None:
        """Close open PR for a flow branch if one exists.

        Returns PR number if closed, None otherwise.
        """
        logger.bind(
            domain="pr",
            action="close_open_pr_for_flow",
            branch=branch,
        ).info("Checking for open PR to close")

        pr = self.get_open_pr_for_branch(branch)
        if not pr:
            logger.bind(branch=branch).info("No open PR found for branch")
            return None

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

        # Update PR context cache with latest PR info using IssueTitleCacheService
        from vibe3.services.issue_title_cache_service import IssueTitleCacheService

        title_cache = IssueTitleCacheService(self.store)
        title_cache.update_pr(
            branch=pr.head_branch,
            pr_number=pr.number,
            pr_title=pr.title,
        )
