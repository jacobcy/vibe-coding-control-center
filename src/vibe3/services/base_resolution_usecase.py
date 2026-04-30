"""Shared base-resolution helpers for command-facing use cases."""

from dataclasses import dataclass
from typing import Callable, Literal

from vibe3.clients.git_client import GitClient, GitClientProtocol
from vibe3.exceptions import UserError
from vibe3.models.change_source import BranchSource
from vibe3.utils.branch_utils import find_parent_branch

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
    ) -> None:
        self.parent_branch_finder = parent_branch_finder
        self.git_client = git_client or GitClient()

    @staticmethod
    def resolve_pr_create_base(requested_base: str | None) -> str:
        """Resolve base branch for PR creation while preserving current default."""
        return requested_base or MAIN_BRANCH_NAME

    def resolve_inspect_base(
        self,
        requested_base: str | None,
        current_branch: str,
    ) -> ResolvedBase:
        """Resolve base branch for inspect-base mode."""
        return self.resolve_base(
            requested_base=requested_base,
            current_branch=current_branch,
            default_policy="parent",
        )

    def resolve_review_base(
        self,
        requested_base: str | None,
        current_branch: str,
    ) -> ResolvedBase:
        """Resolve base branch for review-base mode."""
        return self.resolve_base(
            requested_base=requested_base,
            current_branch=current_branch,
            default_policy="parent",
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
    ) -> ResolvedBase:
        """Resolve base branch using unified policy tokens.

        Supported policy tokens:
        - parent: closest parent branch inferred from topology
        - current: current branch
        - main: origin/main
        """
        token = (requested_base or default_policy).strip()
        if token == "parent":
            inferred = self.parent_branch_finder(current_branch)
            if inferred is None:
                raise UserError(
                    "Could not auto-detect parent branch. "
                    "Please specify base branch explicitly."
                )
            return ResolvedBase(base_branch=inferred, auto_detected=True)
        if token == "current":
            return ResolvedBase(base_branch=current_branch, auto_detected=False)
        if token == "main":
            return ResolvedBase(base_branch=MAIN_BRANCH_REF, auto_detected=False)
        return ResolvedBase(base_branch=token, auto_detected=False)

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
