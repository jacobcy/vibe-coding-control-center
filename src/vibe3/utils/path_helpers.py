"""Path helper utilities for normalization and resolution."""

from pathlib import Path
from typing import Protocol


class GitClientProtocol(Protocol):
    """Protocol for git client operations."""

    def get_git_common_dir(self) -> str: ...
    def get_worktree_root(self) -> str: ...
    def find_worktree_path_for_branch(self, branch: str) -> Path | None: ...
    def get_current_branch(self) -> str: ...


def _get_git_client(git_client: GitClientProtocol | None = None) -> GitClientProtocol:
    """Get or create a GitClient instance.

    Factory function to avoid repeating GitClient initialization logic.
    Uses cached singleton when no explicit client is provided.
    """
    if git_client is None:
        from vibe3.clients.git_client import get_git_client

        return get_git_client()
    return git_client


def get_git_common_dir(git_client: GitClientProtocol | None = None) -> str:
    """Get the shared git common directory (.git/)."""
    git_client = _get_git_client(git_client)
    try:
        return git_client.get_git_common_dir()
    except (OSError, ValueError):
        return ""


def get_worktree_root(git_client: GitClientProtocol | None = None) -> str:
    """Get the current worktree root."""
    git_client = _get_git_client(git_client)
    try:
        return git_client.get_worktree_root()
    except (OSError, ValueError):
        return ""


def find_worktree_path_for_branch(
    branch: str, git_client: GitClientProtocol | None = None
) -> Path | None:
    """Find the worktree path for a specific branch."""
    git_client = _get_git_client(git_client)
    try:
        return git_client.find_worktree_path_for_branch(branch)
    except (OSError, ValueError):
        return None


class BranchBoundGitClient:
    """Git client shim that pins operations to an explicit branch."""

    def __init__(self, branch: str) -> None:
        self._branch = branch
        self._delegate = _get_git_client()

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

    git_client = _get_git_client(git_client)

    # Try branch worktree root
    worktree_root: Path | None = None
    try:
        worktree_root = git_client.find_worktree_path_for_branch(branch)
    except (OSError, ValueError):
        worktree_root = None

    if worktree_root is None:
        try:
            current_root = git_client.get_worktree_root()
        except (OSError, ValueError):
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
    except (OSError, ValueError):
        pass

    return ref_value


def _resolve_absolute_path(
    ref_path: Path,
    root_path: Path,
    absolute: bool,
) -> str:
    """Resolve absolute path to relative or absolute form.

    Priority:
    1. Relative to worktree root (agent's local files)
    2. Relative to git common dir (shared artifacts)
    3. Return as absolute path
    """
    if absolute:
        return str(ref_path)

    # Priority 1: Relative to worktree root (agent's local files)
    try:
        return str(ref_path.relative_to(root_path))
    except ValueError:
        pass

    # Priority 2: Relative to git common dir (shared artifacts)
    try:
        git_common = Path(_get_git_client().get_git_common_dir())
        if git_common and str(ref_path).startswith(str(git_common)):
            return str(ref_path.relative_to(git_common))
    except (OSError, ValueError):
        pass

    # Priority 3: Pattern-based extraction for cross-machine handoff paths
    path_str = str(ref_path)
    if _SHARED_HANDOFF_PREFIX in path_str:
        # Extract relative path starting from vibe3/handoff/
        idx = path_str.find(_SHARED_HANDOFF_PREFIX)
        return path_str[idx:]

    return str(ref_path)


def _resolve_relative_path(
    ref_path: Path,
    root_path: Path,
    absolute: bool,
) -> str:
    """Resolve relative path by checking worktree and git common dir.

    Priority:
    1. Worktree root (usually local files like docs/plans)
    2. Git common dir (usually shared artifacts in .git/vibe3)
    3. Return as-is
    """
    # Priority 1: Worktree root (usually local files like docs/plans)
    worktree_resolved = root_path / ref_path
    if worktree_resolved.exists():
        return str(worktree_resolved.absolute()) if absolute else str(ref_path)

    # Priority 2: Git common dir (usually shared artifacts in .git/vibe3)
    try:
        git_common = Path(_get_git_client().get_git_common_dir())
        if git_common:
            git_resolved = git_common / ref_path
            if git_resolved.exists():
                return str(git_resolved.absolute()) if absolute else str(ref_path)
    except (OSError, ValueError):
        pass

    # Fallback: return as-is
    return str(ref_path)


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

        # Resolve worktree root
        if not worktree_root:
            try:
                worktree_root = _get_git_client().get_worktree_root()
            except (OSError, ValueError):
                worktree_root = ""

        root_path = Path(worktree_root) if worktree_root else Path.cwd()

        # Dispatch to specialized resolvers
        if ref_path.is_absolute():
            return _resolve_absolute_path(ref_path, root_path, absolute)
        else:
            return _resolve_relative_path(ref_path, root_path, absolute)
    except Exception:
        # Fallback: just show the raw value
        return ref_value


_SHARED_HANDOFF_PREFIX = "vibe3/handoff/"


def check_ref_exists(
    ref_value: str,
    branch: str | None = None,
    git_client: GitClientProtocol | None = None,
) -> tuple[str, bool]:
    """Check if a reference path exists, unified method for all callers.

    This is the single source of truth for reference file existence checks.
    Used by check_service.py (flow verification) and flow_ui_timeline.py (display).

    Args:
        ref_value: The reference string to check (path, @key, or absolute)
        branch: Optional branch for worktree resolution
        git_client: Optional git client (defaults to new GitClient)

    Returns:
        Tuple of (display_path, exists):
        - display_path: Relative path for display (or original if cannot relativize)
        - exists: True if the file exists in the correct worktree context
    """
    try:
        resolved_path = resolve_handoff_target(ref_value, branch, git_client)
        exists = resolved_path.exists()

        # Get display path (relative if possible)
        git_client = _get_git_client(git_client)

        # Try to make relative to worktree or git common for display
        display = ref_value
        if resolved_path.is_absolute():
            # Try worktree root
            try:
                wt_root = (
                    find_worktree_path_for_branch(branch, git_client)
                    if branch
                    else None
                )
                if wt_root is None:
                    wt_root = Path(get_worktree_root(git_client))
                if wt_root:
                    display = str(resolved_path.relative_to(wt_root))
            except ValueError:
                # Try git common dir
                try:
                    git_common = Path(get_git_common_dir(git_client))
                    if str(resolved_path).startswith(str(git_common)):
                        display = str(resolved_path.relative_to(git_common))
                except (OSError, ValueError):
                    pass

        return (display, exists)

    except FileNotFoundError:
        # File doesn't exist or worktree missing
        return (ref_value, False)
    except Exception:
        # Any other error: assume doesn't exist
        return (ref_value, False)


def _resolve_shared_artifact(
    target: str,
    git_client: GitClientProtocol,
) -> Path:
    """Resolve @prefix shared artifact path.

    Args:
        target: Target string with @ prefix (e.g., "@task-xxx/run.md")
        git_client: Git client for path resolution

    Returns:
        Absolute path to the shared artifact

    Raises:
        FileNotFoundError: If git common dir unavailable or artifact not found
    """
    key = target[1:]  # Strip @ prefix
    git_common = get_git_common_dir(git_client)
    if not git_common:
        raise FileNotFoundError(
            f"Cannot resolve shared artifact without git common dir: {target}"
        )
    resolved = Path(git_common) / "vibe3" / "handoff" / key
    if not resolved.exists():
        raise FileNotFoundError(f"Shared artifact not found: {target}")
    return resolved


def _resolve_worktree_artifact(
    target: str,
    branch: str | None,
    git_client: GitClientProtocol,
) -> Path:
    """Resolve worktree-relative artifact path.

    Args:
        target: Relative path to artifact
        branch: Optional branch name for strict worktree resolution
        git_client: Git client for path resolution

    Returns:
        Absolute path to the artifact

    Raises:
        FileNotFoundError: If artifact not found in any worktree context
    """
    if branch:
        # Strict mode: when branch is explicitly given, only resolve within
        # that branch's worktree. Never fall back to current worktree or CWD,
        # as that would silently return a file from the wrong flow.
        wt_path = find_worktree_path_for_branch(branch, git_client)
        if wt_path is None:
            raise FileNotFoundError(f"No worktree found for branch '{branch}'")
        resolved = wt_path / target
        if not resolved.exists():
            raise FileNotFoundError(
                f"Artifact not found in branch '{branch}' worktree: {target}"
            )
        return resolved

    # No branch specified: try current worktree then CWD
    current_root = get_worktree_root(git_client)
    if current_root:
        resolved = Path(current_root) / target
        if resolved.exists():
            return resolved

    # Also try CWD (handles cases where CWD differs from worktree root)
    cwd_resolved = Path.cwd() / target
    if cwd_resolved.exists():
        return cwd_resolved

    raise FileNotFoundError(f"Artifact not found: {target}")


def resolve_handoff_target(
    target: str,
    branch: str | None = None,
    git_client: GitClientProtocol | None = None,
) -> Path:
    """Resolve a handoff show target into an absolute file path.

    Three namespaces:

    1. ``@prefix/key`` → shared handoff artifact under ``.git/vibe3/handoff/``.
       The ``@`` is stripped and the remainder is joined to the handoff dir.
       ``branch`` is ignored for shared artifacts.

    2. ``relative/path`` → canonical worktree ref.
       Resolved against the target branch's worktree root (or current worktree
       when ``branch`` is None).

    3. ``/abs/path`` → absolute path passthrough (debug fallback).

    Raises:
        FileNotFoundError: If the resolved path does not exist.
    """
    git_client = _get_git_client(git_client)

    # Namespace 1: @ prefix → shared handoff store
    if target.startswith("@"):
        return _resolve_shared_artifact(target, git_client)

    # Namespace 1.5: vibe3/handoff/ prefix → shared handoff store (no @ needed)
    # This handles refs stored by record_passive_artifact that don't have @ prefix
    if target.startswith(_SHARED_HANDOFF_PREFIX):
        # Convert vibe3/handoff/task-xxx/run.md → @task-xxx/run.md
        return _resolve_shared_artifact(
            "@" + target[len(_SHARED_HANDOFF_PREFIX) :], git_client
        )

    target_path = Path(target)

    # Namespace 3: absolute path → passthrough
    if target_path.is_absolute():
        if not target_path.exists():
            raise FileNotFoundError(f"File not found: {target}")
        return target_path

    # Namespace 2: relative path → worktree canonical ref
    return _resolve_worktree_artifact(target, branch, git_client)


def is_shared_handoff_ref(ref_value: str) -> bool:
    """Return True if the stored ref points to a shared handoff artifact."""
    return ref_value.startswith(_SHARED_HANDOFF_PREFIX)


def to_display_target(ref_value: str) -> str:
    """Convert a stored ref value to a display target for ``handoff show``.

    ``vibe3/handoff/task-xxx/run.md`` → ``@task-xxx/run.md``
    Other relative paths → returned as-is (canonical worktree ref).
    Absolute paths → returned as-is.
    """
    if ref_value.startswith(_SHARED_HANDOFF_PREFIX):
        return "@" + ref_value[len(_SHARED_HANDOFF_PREFIX) :]
    return ref_value


def ref_to_handoff_cmd(path: str, branch: str | None = None) -> str:
    """Convert a display-form ref path to a ``vibe3 handoff show`` command.

    Call ``resolve_ref_path(abs_path, worktree_root)`` first to strip the
    worktree prefix before passing the result here.

    Shared artifacts (``vibe3/handoff/...``) get the ``@`` prefix form.
    Canonical worktree refs (``docs/reports/...``, ``docs/plans/...``) get
    ``--branch <branch>`` when branch is known.
    Other relative paths and absolute paths are returned as-is (not handoff artifacts).
    """
    if is_shared_handoff_ref(path):
        return f"vibe3 handoff show {to_display_target(path)}"
    # Only treat docs/reports and docs/plans as handoff artifacts
    if path.startswith("docs/reports/") or path.startswith("docs/plans/"):
        if branch:
            return f"vibe3 handoff show --branch {branch} {path}"
        return f"vibe3 handoff show {path}"
    # Non-handoff paths (temp/logs, etc.) return as-is
    return path


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
