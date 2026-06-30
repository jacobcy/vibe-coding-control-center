"""Handoff target resolution utilities.

This module handles the resolution of handoff targets into absolute file paths.

Four namespaces are supported:

1. ``@vibe/<path>`` → vibe3 installation materials.
   Resolves to governance materials under the vibe3 installation root.

2. ``@prefix/key`` → shared handoff artifact under ``.git/vibe3/handoff/``.
   The ``@`` is stripped and the remainder is joined to the handoff dir.
   Special case: ``@current`` with ``--branch`` resolves to per-branch current.md.
   Special case: ``@plan/@report/@audit`` resolve from flow_state refs.

3. ``relative/path`` → canonical worktree ref.
   Resolved against the target branch's worktree root (or current worktree
   when ``branch`` is None).

4. ``/abs/path`` → absolute path passthrough (debug fallback).
"""

import re
from pathlib import Path

from vibe3.services.shared.paths import (
    _SHARED_HANDOFF_PREFIX,
    GitPathProtocol,
    _get_git_client,
    find_worktree_path_for_branch,
    get_git_common_dir,
    get_worktree_root,
)

# Branch name validation regex: alphanumeric, slash, underscore, hyphen, period, colon
# Note: re.fullmatch() ensures the entire string matches, preventing control
# characters like trailing newlines from being accepted
_BRANCH_NAME_PATTERN = re.compile(r"[a-zA-Z0-9/_.:-]+")

# Vibe path validation regex: alphanumeric, slash, underscore, hyphen, period, colon
# Used for @vibe/<path> namespace to prevent path traversal attacks
_VIBE_PATH_PATTERN = re.compile(r"[a-zA-Z0-9/_.:-]+")


def _validate_branch_name(branch: str) -> None:
    """Validate branch name to prevent path traversal attacks.

    Args:
        branch: Branch name to validate

    Raises:
        ValueError: If branch name is invalid (contains .., control chars, or empty)
    """
    if not branch or not branch.strip():
        raise ValueError("Invalid branch name: branch cannot be empty or whitespace")

    if ".." in branch:
        raise ValueError(
            f"Invalid branch name {branch!r}: contains path traversal sequence '..'"
        )

    if not _BRANCH_NAME_PATTERN.fullmatch(branch):
        raise ValueError(
            f"Invalid branch name {branch!r}: contains invalid characters. "
            f"Only alphanumeric, '/', '_', '-', '.', and ':' are allowed."
        )


def _validate_vibe_path(path: str) -> None:
    """Validate @vibe/<path> to prevent path traversal attacks.

    Args:
        path: Path component after @vibe/ to validate

    Raises:
        ValueError: If path is invalid (contains .., control chars, or empty)
    """
    if not path or not path.strip():
        raise ValueError("Invalid @vibe target: path cannot be empty")

    if ".." in path.split("/"):
        raise ValueError(
            f"Invalid @vibe target {path!r}: contains path traversal sequence '..'"
        )

    if not _VIBE_PATH_PATTERN.fullmatch(path):
        raise ValueError(
            f"Invalid @vibe target {path!r}: contains invalid characters. "
            f"Only alphanumeric, '/', '_', '-', '.', and ':' are allowed."
        )


def _verify_handoff_dir_boundary(handoff_dir: Path, git_common: str) -> None:
    """Verify that resolved handoff directory stays within handoff root.

    Args:
        handoff_dir: Resolved handoff directory path
        git_common: Git common directory path (.git/)

    Raises:
        ValueError: If resolved path is outside handoff root
    """
    handoff_root = Path(git_common) / "vibe3" / "handoff"
    resolved_handoff = handoff_dir.resolve()
    resolved_root = handoff_root.resolve()

    try:
        resolved_handoff.relative_to(resolved_root)
    except ValueError:
        raise ValueError(
            f"Security violation: resolved handoff directory {resolved_handoff} "
            f"escapes handoff root {resolved_root}"
        )


def _resolve_vibe_material(
    target: str,
    vibe_dir: str | None = None,
) -> Path:
    """Resolve @vibe/<path> to vibe3 installation directory.

    Args:
        target: Target string with @vibe/ prefix
        vibe_dir: Optional explicit vibe3 installation path

    Returns:
        Absolute path to the material file

    Raises:
        ValueError: If path validation fails
        FileNotFoundError: If file not found or is a directory
    """
    # Extract path after @vibe/ prefix
    material_path = target[6:]  # len("@vibe/") == 6
    _validate_vibe_path(material_path)

    # Priority 1: Explicit vibe_dir parameter
    if vibe_dir:
        vibe_path = Path(vibe_dir)
        if not vibe_path.exists():
            raise FileNotFoundError(
                f"Specified vibe_dir does not exist: {vibe_dir}\n\n"
                "The --vibe-dir path must point to an existing vibe3 installation."
            )
        resolved = (vibe_path / material_path).resolve()
        vibe_path_resolved = vibe_path.resolve()

        # Boundary check: ensure resolved path stays within vibe root
        try:
            resolved.relative_to(vibe_path_resolved)
        except ValueError:
            raise ValueError(
                f"Security violation: resolved path escapes vibe root: {resolved}"
            )

        if not resolved.exists():
            raise FileNotFoundError(
                f"Material not found: {target}\n\n"
                f"File does not exist: {resolved}\n"
                "Check the path or view available materials in the vibe3 installation."
            )
        if not resolved.is_file():
            raise FileNotFoundError(
                f"Not a file: {target}\n\n"
                f"Path points to a directory: {resolved}\n"
                "Materials must be files, not directories."
            )

        return resolved

    # Priorities 2 & 3: Auto-detection via unified resolver
    # Inline import to avoid circular dependency with clients module
    from vibe3.clients import (
        bundled_project_root,
        resolve_runtime_asset,
        runtime_assets_root,
    )

    resolved = resolve_runtime_asset(material_path, namespace="vibe")

    # Defense-in-depth: verify resolved path stays within allowed roots
    # (Already guaranteed by resolve_runtime_asset construction + _validate_vibe_path)
    bundled_root = bundled_project_root().resolve()
    global_root = runtime_assets_root().resolve()
    resolved_normalized = resolved.resolve()

    try:
        resolved_normalized.relative_to(bundled_root)
    except ValueError:
        try:
            resolved_normalized.relative_to(global_root)
        except ValueError:
            raise ValueError(
                f"Security violation: resolved path escapes vibe roots: {resolved}"
            )

    if not resolved.exists():
        raise FileNotFoundError(
            f"Material not found: {target}\n\n"
            f"File does not exist: {resolved}\n"
            "Check the path or view available materials in the vibe3 installation."
        )
    if not resolved.is_file():
        raise FileNotFoundError(
            f"Not a file: {target}\n\n"
            f"Path points to a directory: {resolved}\n"
            "Materials must be files, not directories."
        )

    return resolved


def _resolve_shared_artifact(
    target: str,
    branch: str | None = None,
    git_client: GitPathProtocol | None = None,
) -> Path:
    """Resolve @prefix shared artifact path.

    Args:
        target: Target string with @ prefix (e.g., "@current", "@task-xxx/run.md")
        branch: Optional branch for per-branch artifact resolution (e.g., @current)
        git_client: Git client for path resolution

    Returns:
        Absolute path to the shared artifact

    Raises:
        FileNotFoundError: If git common dir unavailable or artifact not found
    """
    git_client = _get_git_client(git_client)
    key = target[1:]  # Strip @ prefix

    # Special handling for @current (per-branch artifact)
    if key == "current":
        from vibe3.utils import get_branch_handoff_dir

        if not branch:
            # Try to get current branch if not specified
            try:
                branch = git_client.get_current_branch()
            except Exception:
                raise FileNotFoundError(
                    f"Cannot resolve @current without branch "
                    f"specification: {target}\n\n"
                    "@current requires a branch context to locate "
                    "per-branch handoff file.\n"
                    "Specify branch: vibe3 handoff show @current "
                    "--branch <branch-name>\n"
                    "Or run from a branch: git checkout <branch> "
                    "&& vibe3 handoff show @current"
                )

        # Validate branch name to prevent path traversal attacks
        _validate_branch_name(branch)

        # Resolve @current to per-branch current.md
        git_common = get_git_common_dir(git_client)
        if not git_common:
            raise FileNotFoundError(
                f"Cannot resolve shared artifact without git common dir: {target}"
            )

        handoff_dir = get_branch_handoff_dir(git_common, branch)

        # Verify resolved path stays within handoff root (defense in depth)
        _verify_handoff_dir_boundary(handoff_dir, git_common)

        current_md = handoff_dir / "current.md"
        if not current_md.exists():
            raise FileNotFoundError(
                f"current.md not found for branch '{branch}': {target}\n\n"
                "No handoff file has been created for this branch yet.\n"
                f"Create one: vibe3 handoff init --branch {branch}"
            )
        if not current_md.is_file():
            raise FileNotFoundError(f"Not a file: {target}")
        return current_md

    # Special handling for @plan/@report/@audit/@spec/@indicate aliases
    if key in ("plan", "report", "audit", "spec", "indicate"):
        return _resolve_artifact_alias(key, f"{key}_ref", branch, git_client)

    # Standard shared artifact (not @current, @plan, @report, or @audit)
    git_common = get_git_common_dir(git_client)
    if not git_common:
        raise FileNotFoundError(
            f"Cannot resolve shared artifact without git common dir: {target}\n\n"
            "Git repository not initialized or .git directory not found.\n"
            "Run this command inside a git repository."
        )

    # Validate key to prevent path traversal attacks
    _validate_branch_name(key)

    resolved = Path(git_common) / "vibe3" / "handoff" / key

    # Defense in depth — ensure resolved path stays within handoff root
    _verify_handoff_dir_boundary(resolved, git_common)

    if not resolved.exists():
        raise FileNotFoundError(
            f"Artifact not found: {target}\n\n"
            "Handoff targets support three namespaces:\n"
            "  @key              Shared artifact (.git/vibe3/handoff/)\n"
            "  relative/path     Worktree ref (requires --branch for other branches)\n"
            "  /abs/path         Absolute path (debugging fallback)\n\n"
            "View available artifacts: vibe3 handoff status"
        )
    if not resolved.is_file():
        raise FileNotFoundError(
            f"Not a file: {target}\n\n"
            "Handoff targets must point to files, not directories.\n"
            "View available artifacts: vibe3 handoff status"
        )
    return resolved


def _resolve_artifact_alias(
    alias: str,
    ref_field: str,
    branch: str | None,
    git_client: GitPathProtocol,
) -> Path:
    """Resolve @plan/@report/@audit alias from flow_state.

    Args:
        alias: Alias name (plan, report, or audit)
        ref_field: Field name in flow_state (plan_ref, report_ref, or audit_ref)
        branch: Optional branch name
        git_client: Git client for path resolution

    Returns:
        Absolute path to the artifact

    Raises:
        FileNotFoundError: If flow not found or ref field not set
        ValueError: If ref value is self-referential (would cause infinite recursion)
    """
    from vibe3.clients import SQLiteClient

    if not branch:
        branch = git_client.get_current_branch()
        if not branch:
            raise FileNotFoundError(
                f"Cannot resolve @{alias} without branch: no current branch\n\n"
                f"@{alias} requires branch context to look up flow state.\n"
                "Specify branch: vibe3 handoff show @{alias} "
                "--branch <branch-name>\n"
                "Or run from a branch: git checkout <branch> "
                f"&& vibe3 handoff show @{alias}"
            )

    _validate_branch_name(branch)

    store = SQLiteClient()
    flow = store.get_flow_state(branch)
    if not flow:
        raise FileNotFoundError(
            f"No flow found for branch '{branch}'\n\n"
            f"@{alias} requires an active flow to resolve the artifact path.\n"
            f"Create a flow: vibe3 flow update --branch {branch}\n"
            "Or view available flows: vibe3 flow status"
        )

    ref_value = flow.get(ref_field)
    if not ref_value:
        raise FileNotFoundError(
            f"No {ref_field} recorded for branch '{branch}'\n\n"
            f"This flow has not created a {alias} artifact yet.\n"
            f"Check flow status: vibe3 flow show --branch {branch}\n"
            f"View all handoff events: vibe3 handoff status --branch {branch}"
        )

    # Guard against self-referential alias values (e.g., plan_ref='@plan')
    # which would cause infinite recursion via resolve_handoff_target
    if ref_value in ("@plan", "@report", "@audit", "@spec", "@current", "@indicate"):
        raise ValueError(
            f"Invalid {ref_field}: self-referential alias {ref_value!r} "
            f"would cause infinite recursion"
        )

    return resolve_handoff_target(ref_value, branch, git_client)


def _resolve_worktree_artifact(
    target: str,
    branch: str | None,
    git_client: GitPathProtocol,
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
            raise FileNotFoundError(
                f"No worktree found for branch '{branch}'\n\n"
                "The specified branch does not have a worktree.\n"
                f"Create worktree: git worktree add <path> {branch}\n"
                f"Or use current branch: vibe3 handoff show {target}"
            )
        resolved = wt_path / target
        if not resolved.exists():
            raise FileNotFoundError(
                f"File not found in branch '{branch}' worktree: {target}\n\n"
                "The file does not exist in the specified branch's worktree.\n"
                "Check file path or view handoff status: "
                f"vibe3 handoff status --branch {branch}"
            )
        if not resolved.is_file():
            raise FileNotFoundError(f"Not a file: {target}")
        return resolved

    # No branch specified: try current worktree then CWD
    current_root = get_worktree_root(git_client)
    if current_root:
        resolved = Path(current_root) / target
        if resolved.exists():
            if resolved.is_file():
                return resolved
            else:
                raise FileNotFoundError(f"Not a file: {target}")

    # Also try CWD (handles cases where CWD differs from worktree root)
    cwd_resolved = Path.cwd() / target
    if cwd_resolved.exists():
        if cwd_resolved.is_file():
            return cwd_resolved
        else:
            raise FileNotFoundError(f"Not a file: {target}")

    raise FileNotFoundError(f"Artifact not found: {target}")


def resolve_handoff_target(
    target: str,
    branch: str | None = None,
    git_client: GitPathProtocol | None = None,
    vibe_dir: str | None = None,
) -> Path:
    """Resolve a handoff show target into an absolute file path.

    Four namespaces:

    1. ``@vibe/<path>`` → vibe3 installation materials.
       Resolves to governance materials under the vibe3 installation root.

    2. ``@prefix/key`` → shared handoff artifact under ``.git/vibe3/handoff/``.
       The ``@`` is stripped and the remainder is joined to the handoff dir.
       Special cases requiring branch context (explicit or current):
       - ``@current`` → per-branch current.md
       - ``@plan/@report/@audit/@spec`` → resolved from flow_state refs
       Other shared artifacts (``@task-xxx/run.md``) ignore branch.

    3. ``relative/path`` → canonical worktree ref.
       Resolved against the target branch's worktree root (or current worktree
       when ``branch`` is None).

    4. ``/abs/path`` → absolute path passthrough (debug fallback).

    Args:
        target: Target string to resolve
        branch: Optional branch for per-branch artifact resolution
        git_client: Git client for path resolution
        vibe_dir: Optional explicit vibe3 installation path for @vibe/ targets

    Raises:
        FileNotFoundError: If the resolved path does not exist.
    """
    git_client = _get_git_client(git_client)

    # Namespace 0: @vibe/<path> → vibe3 installation materials
    if target.startswith("@vibe/"):
        return _resolve_vibe_material(target, vibe_dir)

    # Namespace 1: @ prefix → shared handoff store
    if target.startswith("@"):
        return _resolve_shared_artifact(target, branch, git_client)

    # Namespace 1.5: vibe3/handoff/ prefix → shared handoff store (no @ needed)
    # This handles refs stored by record_passive_artifact that don't have @ prefix
    if target.startswith(_SHARED_HANDOFF_PREFIX):
        # Convert vibe3/handoff/task-xxx/run.md → @task-xxx/run.md
        return _resolve_shared_artifact(
            "@" + target[len(_SHARED_HANDOFF_PREFIX) :], branch, git_client
        )

    target_path = Path(target)

    # Namespace 3: absolute path → passthrough
    if target_path.is_absolute():
        if not target_path.exists():
            raise FileNotFoundError(f"Artifact not found: {target}")
        if not target_path.is_file():
            raise FileNotFoundError(f"Not a file: {target}")
        return target_path

    # Namespace 2: relative path → worktree canonical ref
    return _resolve_worktree_artifact(target, branch, git_client)
