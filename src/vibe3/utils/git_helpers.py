"""Git helper utilities."""

import configparser
import functools
import hashlib
import subprocess
from pathlib import Path

from loguru import logger

# Delayed import to avoid utils → exceptions circular dependency
# from vibe3.exceptions import GitError


class RepositoryLayoutError(RuntimeError):
    """Raised when repository topology cannot be resolved safely."""


def _layout_error(
    *,
    reason: str,
    git_common_dir: Path,
    cwd: Path | None = None,
    worktree_root: Path | None = None,
) -> RepositoryLayoutError:
    """Build an actionable repository-layout diagnostic."""
    return RepositoryLayoutError(
        "Cannot resolve repository management root: "
        f"{reason}; cwd={cwd or Path.cwd()}; git_common_dir={git_common_dir}; "
        f"worktree_root={worktree_root or 'unavailable'}"
    )


def resolve_repo_root_from_common_dir(
    git_common: str | Path,
    *,
    cwd: Path | None = None,
    worktree_root: Path | None = None,
) -> Path:
    """Resolve a repository management root from its Git common directory.

    A non-bare repository stores its common directory at ``<root>/.git``.
    A bare repository uses the repository directory itself as the common
    directory. Only ``core.bare`` is authoritative; similarly named keys in
    other sections must not affect topology detection.
    """
    common = Path(git_common).expanduser().resolve()
    config_path = common / "config"

    parser = configparser.RawConfigParser(
        interpolation=None,
        strict=False,
        allow_no_value=True,
    )
    if config_path.is_file():
        try:
            with config_path.open(encoding="utf-8") as config_file:
                parser.read_file(config_file)
        except (OSError, UnicodeError, configparser.Error) as exc:
            raise _layout_error(
                reason=f"cannot read Git config {config_path}: {exc}",
                git_common_dir=common,
                cwd=cwd,
                worktree_root=worktree_root,
            ) from exc
    elif common.name != ".git":
        raise _layout_error(
            reason=f"Git config is missing or unreadable: {config_path}",
            git_common_dir=common,
            cwd=cwd,
            worktree_root=worktree_root,
        )

    core_section = next(
        (section for section in parser.sections() if section.casefold() == "core"),
        None,
    )
    if core_section is not None and parser.has_option(core_section, "bare"):
        try:
            is_bare = parser.getboolean(core_section, "bare")
        except ValueError as exc:
            raise _layout_error(
                reason=f"invalid core.bare value in {config_path}: {exc}",
                git_common_dir=common,
                cwd=cwd,
                worktree_root=worktree_root,
            ) from exc
        return common if is_bare else common.parent

    if common.name == ".git":
        return common.parent

    raise _layout_error(
        reason=f"core.bare is not set in {config_path}",
        git_common_dir=common,
        cwd=cwd,
        worktree_root=worktree_root,
    )


def get_branch_handoff_dir(git_dir: str, branch: str) -> Path:
    """Get handoff directory for a specific branch.

    Creates a unique directory path for branch handoff files, using sanitized
    branch name with hash suffix to prevent collisions.

    Args:
        git_dir: Path to .git directory
        branch: Branch name

    Returns:
        Path to .git/vibe3/handoff/<branch-safe>-<hash>/

    Example:
        >>> get_branch_handoff_dir(".git", "feature/api-v2")
        Path(".git/vibe3/handoff/feature-api-v2-a1b2c3d4")
    """
    # Validate branch name
    if not branch or not branch.strip():
        raise ValueError(f"Invalid branch name: {branch!r}")

    # Sanitize branch name with hash suffix to prevent collisions
    # Example: feature/api-v2 and feature/api/v2 would otherwise collide
    branch_hash = hashlib.sha256(branch.encode()).hexdigest()[:8]
    # Replace path separators, remove leading/trailing special chars
    branch_safe = branch.replace("/", "-").replace("\\", "-").strip("-_.")
    # Fallback if branch name becomes empty after sanitization
    if not branch_safe:
        branch_safe = "default"
    # Append hash suffix for uniqueness
    branch_dir = f"{branch_safe}-{branch_hash}"

    result = Path(git_dir) / "vibe3" / "handoff" / branch_dir

    # Log directory computation for debugging
    logger.bind(
        branch=branch,
        branch_hash=branch_hash,
        git_dir=git_dir,
        handoff_dir=str(result),
    ).debug("Computed handoff directory")

    return result


def get_commit_message(sha: str) -> str:
    """Get commit message for a given SHA.

    Args:
        sha: Commit SHA (full or short)

    Returns:
        Commit message string

    Raises:
        GitError: If unable to get commit message
    """
    from vibe3.exceptions import GitError

    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%s", sha],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise GitError(
            operation="log",
            details=f"Failed to get commit message for {sha}: {e.stderr}",
        ) from e


def get_current_branch() -> str:
    """Get current git branch name.

    Returns:
        Branch name string

    Raises:
        GitError: If unable to get current branch
    """
    from vibe3.exceptions import GitError

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise GitError(
            operation="rev-parse", details=f"Failed to get current branch: {e.stderr}"
        ) from e


@functools.lru_cache(maxsize=1)
def get_git_common_dir() -> str:
    """Get the shared .git directory path (for worktrees).

    Standalone subprocess version — no GitClient dependency.
    Used by find_repo_root() to resolve the main repository root.

    Returns:
        Absolute path to .git directory

    Raises:
        GitError: If unable to get git common dir
    """
    from vibe3.exceptions import GitError

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True,
            text=True,
            check=True,
        )
        path = result.stdout.strip()
        if not path:
            raise GitError(
                operation="rev-parse",
                details="git common dir returned empty path",
            )
        return path
    except subprocess.CalledProcessError as e:
        raise GitError(
            operation="rev-parse",
            details=f"Failed to get git common dir: {e.stderr}",
        ) from e


def get_remote_url(name: str = "origin") -> str | None:
    """Get the URL of a git remote.

    Standalone subprocess version — no GitClient dependency.

    Args:
        name: Remote name (default: "origin")

    Returns:
        Remote URL string, or None if remote doesn't exist or not a git repo
    """
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", name],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


@functools.lru_cache(maxsize=1)
def find_repo_root() -> Path:
    """Resolve the main repository root deterministically.

    Never returns a linked worktree root as the main repo — that would cause
    nested-worktree creation and wrong-directory DB access.

    This is the single source of truth for repo root resolution.
    All callers that need the repository root for worktree operations,
    database access, or git command execution must use this function.

    Cached with lru_cache to avoid repeated subprocess calls — the repo root
    cannot change during a process's lifetime.

    Resolution chain:
    1. git rev-parse --git-common-dir (works in main repo and worktrees)
    2. Parse .git file pointer (worktree: gitdir: /path/.git/worktrees/name)
    3. .git is a directory → cwd IS main repo
    4. Walk up directory tree to find .git directory
    5. Raise SystemError if not in a git repository

    Returns:
        Path to the main repository root

    Raises:
        SystemError: If not in a git repository
    """
    # Primary: git common dir (works in both main repo and worktrees)
    try:
        git_common = get_git_common_dir()
        if git_common:
            return resolve_repo_root_from_common_dir(git_common, cwd=Path.cwd())
    except RepositoryLayoutError:
        raise
    except Exception:
        pass

    # Fallback: parse .git file to find main repo from worktree pointer
    # In a worktree, .git is a file containing "gitdir: /path/.git/worktrees/name"
    cwd = Path.cwd()
    git_path = cwd / ".git"
    if git_path.is_file():
        try:
            content = git_path.read_text().strip()
            if content.startswith("gitdir: "):
                raw = content[len("gitdir: ") :]
                gitdir = Path(raw)
                if not gitdir.is_absolute():
                    gitdir = (cwd / gitdir).resolve()
                fallback_common = gitdir.parent.parent
                return resolve_repo_root_from_common_dir(fallback_common, cwd=cwd)
        except RepositoryLayoutError:
            raise
        except (OSError, UnicodeError, ValueError) as exc:
            raise RepositoryLayoutError(
                f"Cannot parse linked-worktree Git pointer: cwd={cwd}; "
                f"git_file={git_path}; error={exc}"
            ) from exc

    # If .git is a directory, cwd IS the main repo
    if git_path.is_dir():
        return resolve_repo_root_from_common_dir(git_path, cwd=cwd)

    # Last resort: walk up to find .git directory
    for parent in cwd.parents:
        if (parent / ".git").is_dir():
            return resolve_repo_root_from_common_dir(parent / ".git", cwd=cwd)

    raise SystemError("Cannot resolve repository root — not inside a git repository")
