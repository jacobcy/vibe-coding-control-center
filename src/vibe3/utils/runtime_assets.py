"""Resolve standard runtime assets from the global Vibe distribution."""

from __future__ import annotations

import os
from pathlib import Path

RUNTIME_ASSETS_ROOT_ENV = "VIBE3_RUNTIME_ASSETS_ROOT"


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


def resolve_runtime_asset(path: str | Path) -> Path:
    """Resolve a standard Vibe runtime asset path.

    Relative paths under ``supervisor/``, ``config/prompts/``, and ``skills/``
    are mechanism assets. Source-tree development uses the bundled project copy;
    cross-project execution uses the global distribution. If the global copy
    has not been synced yet, fall back to the bundled project root.
    """
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate

    relative = Path(candidate)
    if relative.parts[:1] in {("supervisor",), ("config",), ("skills",)}:
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
