"""Path helper utilities for normalization and resolution.

This module provides path normalization, resolution, and display utilities.
For handoff target resolution, see handoff_resolution module.
"""

import re
from pathlib import Path

from vibe3.clients import GitPathProtocol


def _get_git_client(git_client: GitPathProtocol | None = None) -> GitPathProtocol:
    """Get or create a GitClient instance."""
    if git_client is None:
        from vibe3.clients import GitClient

        return GitClient()
    return git_client


def get_git_common_dir(git_client: GitPathProtocol | None = None) -> str:
    """Get the shared git common directory (.git/)."""
    git_client = _get_git_client(git_client)
    try:
        return git_client.get_git_common_dir()
    except (OSError, ValueError):
        return ""


def get_worktree_root(git_client: GitPathProtocol | None = None) -> str:
    """Get the current worktree root."""
    git_client = _get_git_client(git_client)
    try:
        return git_client.get_worktree_root()
    except (OSError, ValueError):
        return ""


def find_worktree_path_for_branch(
    branch: str, git_client: GitPathProtocol | None = None
) -> Path | None:
    """Find the worktree path for a specific branch."""
    git_client = _get_git_client(git_client)
    try:
        return git_client.find_worktree_path_for_branch(branch)
    except (OSError, ValueError):
        return None


# Backward compatibility alias
GitClientProtocol = GitPathProtocol

__all__ = [
    "GitPathProtocol",
    "GitClientProtocol",
    "get_git_common_dir",
    "get_worktree_root",
    "find_worktree_path_for_branch",
    "normalize_ref_path",
    "check_ref_exists",
    "resolve_ref_path",
    "ref_to_handoff_cmd",
    "sanitize_event_detail_paths",
]


def normalize_ref_path(
    ref_value: str,
    branch: str,
    git_client: GitPathProtocol | None = None,
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
    # Lazy import to avoid circular dependency with handoff_resolution
    from vibe3.services.handoff_resolution import _SHARED_HANDOFF_PREFIX

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


def check_ref_exists(
    ref_value: str,
    branch: str | None = None,
    git_client: GitPathProtocol | None = None,
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
    # Lazy import to avoid circular dependency with handoff_resolution
    from vibe3.services.handoff_resolution import resolve_handoff_target

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


REF_FIELD_TO_ALIAS: dict[str, str] = {
    "plan_ref": "@plan",
    "report_ref": "@report",
    "audit_ref": "@audit",
    "indicate_ref": "@indicate",
    "spec_ref": "@spec",
}


def _path_to_alias(path: str) -> str:
    """Convert a ref path to shortcut alias if applicable.

    Args:
        path: Relative path (e.g., "docs/plans/xxx.md" or
            ".git/vibe3/handoff/task-xxx/run-yyy.md")

    Returns:
        Shortcut alias (@plan, @report, @spec, @task-xxx/run-yyy.md) or
        original path
    """
    if path.startswith("docs/plans/"):
        return "@plan"
    if path.startswith("docs/reports/"):
        return "@report"
    if path.startswith("docs/specs/"):
        return "@spec"
    # Shared artifacts: add @ prefix and keep the rest
    if path.startswith("vibe3/handoff/"):
        return f"@{path[14:]}"  # Remove "vibe3/handoff/" prefix, add @
    if ".git/vibe3/handoff/" in path:
        match = re.search(r"\.git/vibe3/handoff/(.+)", path)
        if match:
            return f"@{match.group(1)}"
    return path


def ref_to_handoff_cmd(
    path: str, branch: str | None = None, ref_field: str | None = None
) -> str:
    """Convert a display-form ref path to a ``vibe3 handoff show`` command.

    Call ``resolve_ref_path(abs_path, worktree_root)`` first to strip the
    worktree prefix before passing the result here.

    Args:
        path: Display-form ref path
        branch: Optional branch name for worktree refs
        ref_field: Required ref field name (e.g., "plan_ref", "audit_ref")
            When provided, use field-to-alias mapping instead of path-based heuristic

    Returns:
        Handoff show command string

    Raises:
        ValueError: If ref_field is None or not in REF_FIELD_TO_ALIAS
    """
    # CRITICAL: ref_field is required, no fallback to path-based inference
    if ref_field is None:
        raise ValueError(
            "ref_field is required. "
            "Callers must pass the ref field name (e.g., 'plan_ref', 'audit_ref'). "
            f"Expected one of: {list(REF_FIELD_TO_ALIAS.keys())}"
        )

    if ref_field not in REF_FIELD_TO_ALIAS:
        raise ValueError(
            f"Unknown ref_field: {ref_field}. "
            f"Expected one of: {list(REF_FIELD_TO_ALIAS.keys())}"
        )

    display_target = REF_FIELD_TO_ALIAS[ref_field]

    # Shared artifacts: use @ prefix form without --branch
    if path.startswith("vibe3/handoff/") or ".git/vibe3/handoff/" in path:
        return f"vibe3 handoff show {display_target}"
    # Worktree refs: use --branch when available
    if branch:
        return f"vibe3 handoff show --branch {branch} {display_target}"
    return f"vibe3 handoff show {display_target}"


def sanitize_event_detail_paths(
    detail: str,
    event_refs: object,
    worktree_root: str | None = None,
) -> str:
    """Replace path-like refs embedded in event detail with display-safe values."""
    if not isinstance(event_refs, dict):
        return detail

    sanitized = detail

    # Process all *_ref fields (plan_ref, audit_ref, report_ref, etc.)
    for key, value in event_refs.items():
        if key.endswith("_ref") and isinstance(value, str):
            sanitized = sanitized.replace(value, resolve_ref_path(value, worktree_root))

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
