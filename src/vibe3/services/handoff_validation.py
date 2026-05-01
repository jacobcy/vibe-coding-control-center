"""Validation utilities for handoff service."""

from pathlib import Path
from typing import Callable

from vibe3.exceptions import UserError
from vibe3.utils.path_helpers import GitClientProtocol


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
    git_client: GitClientProtocol,
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
