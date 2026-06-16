"""Shared base-resolution helpers for command-facing use cases."""

from dataclasses import dataclass
from typing import Callable, Literal

from vibe3.clients import GitClient, GitClientProtocol, GitHubClient
from vibe3.exceptions import UserError
from vibe3.models import BranchSource
from vibe3.utils import find_parent_branch, is_branch_merged_to_main

MAIN_BRANCH_NAME = "main"
MAIN_BRANCH_REF = "origin/main"


@dataclass(frozen=True)
class ResolvedBase:
    """Resolved base branch plus minimal command-facing metadata."""

    base_branch: str
    auto_detected: bool = False


@dataclass(frozen=True)
class BranchMaterial:
    """Resolved base plus branch-scoped git material."""

    base_branch: str
    commits: list[str]
    changed_files: list[str]


class BaseResolutionUsecase:
    """Unify command-layer base-branch resolution semantics."""

    BaseDefaultPolicy = Literal["parent", "current", "main"]

    def __init__(
        self,
        parent_branch_finder: Callable[[str | None], str | None] = find_parent_branch,
        git_client: GitClientProtocol | None = None,
        github_client: GitHubClient | None = None,
    ) -> None:
        self.parent_branch_finder = parent_branch_finder
        self.git_client = git_client or GitClient()
        self.github_client = github_client or GitHubClient()

    @staticmethod
    def resolve_pr_create_base(requested_base: str | None) -> str:
        """Resolve base branch for PR creation while preserving current default."""
        return requested_base or MAIN_BRANCH_NAME

    def resolve_inspect_base(
        self,
        requested_base: str | None,
        current_branch: str,
        creation_source: str | None = None,
    ) -> ResolvedBase:
        """Resolve base branch for inspect-base mode."""
        return self.resolve_base(
            requested_base=requested_base,
            current_branch=current_branch,
            default_policy="parent",
            creation_source=creation_source,
        )

    def resolve_review_base(
        self,
        requested_base: str | None,
        current_branch: str,
        creation_source: str | None = None,
    ) -> ResolvedBase:
        """Resolve base branch for review-base mode."""
        return self.resolve_base(
            requested_base=requested_base,
            current_branch=current_branch,
            default_policy="parent",
            creation_source=creation_source,
        )

    def resolve_flow_create_base(
        self,
        requested_base: str | None,
        current_branch: str,
        default_policy: BaseDefaultPolicy,
    ) -> str:
        """Resolve base/start-ref for flow create with status-aware defaults."""
        return self.resolve_base(
            requested_base=requested_base,
            current_branch=current_branch,
            default_policy=default_policy,
        ).base_branch

    def resolve_base(
        self,
        requested_base: str | None,
        current_branch: str,
        default_policy: BaseDefaultPolicy,
        creation_source: str | None = None,
    ) -> ResolvedBase:
        """Resolve base branch using unified policy tokens.

        Supported policy tokens:
        - parent: closest parent branch inferred from topology
        - current: current branch
        - main: origin/main

        If creation_source is provided, it takes precedence over parent detection.
        This ensures we use the static branch creation source rather than
        dynamically calculated topology.

        If no creation_source but branch has an open PR, use PR base as fallback.
        This handles PR review worktrees that lack flow state.
        """
        token = (requested_base or default_policy).strip()

        # Prefer creation_source over dynamic parent detection
        if token == "parent" and creation_source:
            return ResolvedBase(base_branch=creation_source, auto_detected=False)

        # Fallback: Try PR base for review worktrees without flow state
        if token == "parent" and not creation_source:
            pr_base = self._try_get_pr_base(current_branch)
            if pr_base:
                return ResolvedBase(base_branch=pr_base, auto_detected=False)

        if token == "parent":
            inferred = self.parent_branch_finder(current_branch)
            if inferred is None:
                raise UserError(
                    "Could not auto-detect parent branch. "
                    "Please specify base branch explicitly."
                )
            # If detected parent is already merged into main, use origin/main
            if is_branch_merged_to_main(inferred):
                return ResolvedBase(base_branch=MAIN_BRANCH_REF, auto_detected=True)
            return ResolvedBase(base_branch=inferred, auto_detected=True)
        if token == "current":
            return ResolvedBase(base_branch=current_branch, auto_detected=False)
        if token == "main":
            return ResolvedBase(base_branch=MAIN_BRANCH_REF, auto_detected=False)
        return ResolvedBase(base_branch=token, auto_detected=False)

    def _try_get_pr_base(self, branch: str) -> str | None:
        """Try to get base branch from open PR for given branch.

        This is a fallback for PR review worktrees that lack flow state.
        When a PR review worktree is created manually (e.g., via wtnew),
        it doesn't have a creation_source in flow metadata. This method
        attempts to infer the correct base from the existing PR.

        This ensures `inspect base` works correctly in review worktrees
        even when flow metadata is missing.

        Returns None if:
        - No PR found for the branch
        - PR fetch fails (network, auth, etc.)
        - PR has no base_branch

        This is a best-effort fallback, not critical path.
        """
        try:
            pr_info = self.github_client.get_pr(branch=branch)
            if pr_info and pr_info.base_branch:
                # Prefix with origin/ if not already
                base = pr_info.base_branch
                if not base.startswith("origin/"):
                    base = f"origin/{base}"
                return base
        except Exception as e:
            # Defense-in-depth: get_pr normally returns None on errors,
            # but catch any unexpected exceptions to prevent breaking
            # the base resolution flow. Log for debugging.
            import logging

            logging.getLogger(__name__).debug(
                f"PR base fallback failed for {branch}: {e}"
            )
        return None

    def collect_branch_material(
        self,
        base_branch: str,
        branch: str,
    ) -> BranchMaterial:
        """Collect branch-scoped git material against a resolved base."""
        commits = self.git_client.get_commit_subjects(base_branch, branch)
        changed_files = self.git_client.get_changed_files(
            BranchSource(branch=branch, base=base_branch)
        )
        return BranchMaterial(
            base_branch=base_branch,
            commits=commits,
            changed_files=changed_files,
        )
