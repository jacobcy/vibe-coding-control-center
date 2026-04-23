"""Path helper utilities for normalization and resolution."""

from pathlib import Path
from typing import Protocol


class GitClientProtocol(Protocol):
    """Protocol for git client operations."""

    def get_git_common_dir(self) -> str: ...
    def get_worktree_root(self) -> str: ...
    def find_worktree_path_for_branch(self, branch: str) -> Path | None: ...
    def get_current_branch(self) -> str: ...


def get_git_common_dir(git_client: GitClientProtocol | None = None) -> str:
    """Get the shared git common directory (.git/)."""
    if git_client is None:
        from vibe3.clients.git_client import GitClient

        git_client = GitClient()
    try:
        return git_client.get_git_common_dir()
    except Exception:
        return ""


def get_worktree_root(git_client: GitClientProtocol | None = None) -> str:
    """Get the current worktree root."""
    if git_client is None:
        from vibe3.clients.git_client import GitClient

        git_client = GitClient()
    try:
        return git_client.get_worktree_root()
    except Exception:
        return ""


def find_worktree_path_for_branch(
    branch: str, git_client: GitClientProtocol | None = None
) -> Path | None:
    """Find the worktree path for a specific branch."""
    if git_client is None:
        from vibe3.clients.git_client import GitClient

        git_client = GitClient()
    try:
        return git_client.find_worktree_path_for_branch(branch)
    except Exception:
        return None


class BranchBoundGitClient:
    """Git client shim that pins operations to an explicit branch."""

    def __init__(self, branch: str) -> None:
        from vibe3.clients.git_client import GitClient

        self._branch = branch
        self._delegate = GitClient()

    def get_current_branch(self) -> str:
        return self._branch

    def get_git_common_dir(self) -> str:
        return self._delegate.get_git_common_dir()

    def get_worktree_root(self) -> str:
        return self._delegate.get_worktree_root()

    def find_worktree_path_for_branch(self, branch: str) -> Path | None:
        return self._delegate.find_worktree_path_for_branch(branch)


def normalize_ref_path(
    ref_value: str,
    branch: str,
    git_client: GitClientProtocol | None = None,
) -> str:
    """Normalize a path for storage in the database.

    Attempts to make the path relative to:
    1. The target branch's worktree root.
    2. The current worktree root.
    3. The shared git common directory (.git/).

    Returns the normalized relative path if successful, otherwise returns original
    value.
    """
    try:
        ref_path = Path(ref_value)
    except (TypeError, ValueError):
        return ref_value

    if not ref_path.is_absolute():
        return ref_value

    if git_client is None:
        from vibe3.clients.git_client import GitClient

        git_client = GitClient()

    # Try branch worktree root
    worktree_root: Path | None = None
    try:
        worktree_root = git_client.find_worktree_path_for_branch(branch)
    except Exception:
        worktree_root = None

    if worktree_root is None:
        try:
            current_root = git_client.get_worktree_root()
        except Exception:
            current_root = ""
        if current_root:
            worktree_root = Path(current_root)

    if worktree_root:
        try:
            return str(ref_path.relative_to(worktree_root))
        except ValueError:
            pass

    # Try git common dir (for shared artifacts in .git/vibe3)
    try:
        git_common = Path(git_client.get_git_common_dir())
        if git_common:
            try:
                return str(ref_path.relative_to(git_common))
            except ValueError:
                pass
    except Exception:
        pass

    return ref_value


def resolve_ref_path(
    ref_value: str | None,
    worktree_root: str | None = None,
    absolute: bool = False,
) -> str:
    """Resolve a reference path for display.

    Handles absolute paths, worktree-relative paths, and git-common-relative paths.
    Returns a path that is valid and accessible in the current environment if possible.

    Args:
        ref_value: The reference string to resolve.
        worktree_root: Optional worktree root to resolve against.
        absolute: If True, returns absolute path. If False, returns relative path
            when the file is within the worktree or git common dir.
    """
    if not ref_value:
        return ""

    try:
        ref_path = Path(ref_value)

        # 1. Resolve worktree root
        if not worktree_root:
            from vibe3.clients.git_client import GitClient

            try:
                worktree_root = GitClient().get_worktree_root()
            except Exception:
                worktree_root = ""

        root_path = Path(worktree_root) if worktree_root else Path.cwd()

        # 2. Handle Absolute Paths
        if ref_path.is_absolute():
            if not absolute:
                # Priority 1: Relative to worktree root (agent's local files)
                try:
                    return str(ref_path.relative_to(root_path))
                except ValueError:
                    pass

                # Priority 2: Relative to git common dir (shared artifacts)
                try:
                    from vibe3.clients.git_client import GitClient

                    git_common = Path(GitClient().get_git_common_dir())
                    if git_common and str(ref_path).startswith(str(git_common)):
                        return str(ref_path.relative_to(git_common))
                except Exception:
                    pass
            return str(ref_path)

        # 3. Handle Relative Paths (portable format)
        # Priority 1: Worktree root (usually local files like docs/plans)
        worktree_resolved = root_path / ref_path
        if worktree_resolved.exists():
            return str(worktree_resolved.absolute()) if absolute else str(ref_path)

        # Priority 2: Git common dir (usually shared artifacts in .git/vibe3)
        from vibe3.clients.git_client import GitClient

        try:
            git_common = Path(GitClient().get_git_common_dir())
            if git_common:
                git_resolved = git_common / ref_path
                if git_resolved.exists():
                    return str(git_resolved.absolute()) if absolute else str(ref_path)
        except Exception:
            pass

        # Fallback: return as-is
        return ref_value
    except Exception:
        # Fallback: just show the raw value
        return ref_value


def sanitize_event_detail_paths(
    detail: str,
    event_refs: object,
    worktree_root: str | None = None,
) -> str:
    """Replace path-like refs embedded in event detail with display-safe values."""
    if not isinstance(event_refs, dict):
        return detail

    sanitized = detail

    ref = event_refs.get("ref")
    if isinstance(ref, str):
        sanitized = sanitized.replace(ref, resolve_ref_path(ref, worktree_root))

    files = event_refs.get("files")
    if isinstance(files, list):
        for file_ref in files:
            if isinstance(file_ref, str):
                sanitized = sanitized.replace(
                    file_ref, resolve_ref_path(file_ref, worktree_root)
                )

    log_path = event_refs.get("log_path")
    if isinstance(log_path, str):
        sanitized = sanitized.replace(log_path, Path(log_path).name)

    return sanitized
