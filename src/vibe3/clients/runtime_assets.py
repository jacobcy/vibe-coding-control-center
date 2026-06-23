"""Resolve standard runtime assets from the global Vibe distribution."""

from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from pathlib import Path

from vibe3.exceptions import DiagnosticContext, MissingResourceError

RUNTIME_ASSETS_ROOT_ENV = "VIBE3_RUNTIME_ASSETS_ROOT"


@lru_cache(maxsize=1)
def _git_toplevel() -> Path | None:
    """Return the git working tree root, or None if not in a repo.

    Uses `git rev-parse --show-toplevel` which returns the current worktree
    root (not the main repo root). This is correct for .vibe/ paths which
    are checked out per-worktree, not shared across worktrees.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except Exception:
        pass
    return None


def bundled_project_root() -> Path:
    """Return the project root containing the currently imported vibe3 package."""
    return Path(__file__).resolve().parents[3]


def runtime_assets_root() -> Path:
    """Return the global runtime assets root.

    Tests and local development can override this with
    ``VIBE3_RUNTIME_ASSETS_ROOT``. Normal cross-project execution uses
    ``~/.vibe``.
    """
    override = os.environ.get(RUNTIME_ASSETS_ROOT_ENV, "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".vibe"


def resolve_runtime_asset(path: str | Path, namespace: str = "default") -> Path:
    """Resolve a standard Vibe runtime asset path.

    Relative paths under ``supervisor/``, ``config/prompts/``, ``skills/``,
    and ``.agent/`` are mechanism assets. Source-tree development uses the
    bundled project copy; cross-project execution uses the global distribution.
    If the global copy has not been synced yet, fall back to the bundled project
    root.

    Relative paths under ``.vibe/`` are project-scope assets anchored to the
    git working tree root (``git rev-parse --show-toplevel``), ensuring correct
    resolution from both repo root and subdirectories.

    Namespaces:
        ``"default"``: Existing behavior for supervisor/config/skills/.agent paths.
        ``"vibe"``: Resolves ``@vibe/<path>`` aliases — any relative path is
            resolved against the bundled project root first, then falls back
            to the global distribution. Skips prefix-based gating.
    """
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate

    relative = Path(candidate)

    # Handle "vibe" namespace: @vibe/<path> alias resolution
    if namespace == "vibe":
        bundled_path = bundled_project_root() / relative
        try:
            Path.cwd().resolve().relative_to(bundled_project_root())
            if bundled_path.exists():
                return bundled_path
        except ValueError:
            pass

        global_path = runtime_assets_root() / relative
        if global_path.exists():
            return global_path

        return bundled_path

    # Default namespace: prefix-based gating for supervisor/config/skills/.agent/.vibe
    if relative.parts[:1] in {
        ("supervisor",),
        ("config",),
        ("skills",),
        (".agent",),
        (".vibe",),  # project-scope, anchor to git toplevel
    }:
        # Handle .vibe/ paths: resolve against git working tree root
        if relative.parts[:1] == (".vibe",):
            root = _git_toplevel()
            if root is not None:
                return root / relative
            return relative  # not in a git repo, caller handles

        # Existing logic for supervisor/config/skills/.agent
        bundled_path = bundled_project_root() / relative
        try:
            Path.cwd().resolve().relative_to(bundled_project_root())
            if bundled_path.exists():
                return bundled_path
        except ValueError:
            pass

        global_path = runtime_assets_root() / relative
        if global_path.exists():
            return global_path

        if bundled_path.exists():
            return bundled_path

        return global_path

    return relative


def resolve_prompt_config(path: str | Path) -> Path:
    """Resolve prompt configuration through the runtime asset model."""
    return resolve_runtime_asset(path)


def check_runtime_asset(path: str | Path) -> Path:
    """Resolve a runtime asset and raise MissingResourceError if not found.

    Args:
        path: Asset path to resolve

    Returns:
        Resolved path if it exists

    Raises:
        MissingResourceError: If the resolved path does not exist
    """
    resolved = resolve_runtime_asset(path)
    if not resolved.exists():
        raise MissingResourceError(
            resource=str(path),
            context=DiagnosticContext(
                resource_type="runtime-asset",
                search_paths=[
                    str(bundled_project_root() / path),
                    str(runtime_assets_root() / path),
                ],
                profile=None,
                remediation=(
                    "Run `vibe update run` from vibe-center repo or "
                    "re-run `scripts/install.sh`"
                ),
                ref_issue=1924,
            ),
        )
    return resolved
