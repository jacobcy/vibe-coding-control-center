"""Validation utilities for handoff service."""

import re
from pathlib import Path
from typing import Callable

from vibe3.exceptions import UserError
from vibe3.services.shared.paths import GitPathProtocol

# Canonical spec document path: .specify/specs/<NNN-slug>/spec.md (ADR-0006).
# Forward-slash, repository-relative, lowercase slug. This is the single
# authoritative shape accepted on the write path.
_CANONICAL_SPEC_PATH = re.compile(r"^\.specify/specs/[0-9]+-[a-z0-9-]+/spec\.md$")


def is_log_like_path(path: Path) -> bool:
    """Check if path points to execution logs."""
    lowered_parts = [part.lower() for part in path.parts]
    for idx in range(len(lowered_parts) - 1):
        if lowered_parts[idx] == "temp" and lowered_parts[idx + 1] == "logs":
            return True
    return path.name.endswith(".async.log")


def validate_authoritative_ref(
    ref_kind: str,
    ref_value: str,
    branch: str,
    git_client: GitPathProtocol,
    authoritative_kinds: set[str],
    resolve_branch_worktree_root: Callable[[str], Path],
) -> None:
    """Validate that authoritative ref points to valid location.

    Raises:
        UserError: If ref is invalid
    """
    if ref_kind.lower() not in authoritative_kinds:
        return

    worktree_root = resolve_branch_worktree_root(branch).resolve()
    ref_path = Path(ref_value).expanduser()
    resolved = (
        ref_path.resolve(strict=False)
        if ref_path.is_absolute()
        else (worktree_root / ref_path).resolve(strict=False)
    )

    if is_log_like_path(resolved):
        raise UserError(
            f"{ref_kind}_ref cannot point to execution logs under temp/logs: "
            f"{ref_value}"
        )
    git_common = Path(git_client.get_git_common_dir()).resolve()
    if resolved.is_relative_to(git_common):
        raise UserError(
            f"{ref_kind}_ref must point to an agent worktree document, "
            f"not shared handoff store: {ref_value}"
        )
    if not resolved.is_relative_to(worktree_root):
        raise UserError(
            f"{ref_kind}_ref must stay inside the agent worktree: {ref_value}"
        )


def validate_canonical_spec_path(ref_value: str, worktree_root: Path) -> None:
    """Validate that spec_ref is a canonical spec document path.

    The spec_ref MUST be a repository-relative path of the form
    ``.specify/specs/<NNN-slug>/spec.md`` (ADR-0006). This rejects legacy
    issue-ids (``#nnn``), URLs, absolute paths, directories, missing files,
    and non-canonical locations — enforcing the write-strict contract while
    read-side compatibility is preserved by ``SpecRefService``.

    Raises:
        UserError: If ref_value is not a canonical existing spec document
            inside the worktree.
    """
    if not _CANONICAL_SPEC_PATH.match(ref_value):
        raise UserError(
            "spec_ref must be a canonical repository-relative path matching "
            ".specify/specs/<NNN-slug>/spec.md (see ADR-0006); legacy "
            f"issue-ids and other forms are rejected on write: {ref_value}"
        )
    root = worktree_root.resolve()
    resolved = (root / ref_value).resolve(strict=False)
    if not resolved.is_file():
        raise UserError(f"spec_ref must point to an existing regular file: {ref_value}")
    if not resolved.is_relative_to(root):
        raise UserError(f"spec_ref must stay inside the agent worktree: {ref_value}")
