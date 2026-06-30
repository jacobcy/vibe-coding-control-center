"""Resource-root resolution helpers for adapter-managed files."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable


class ResourceRootNotFoundError(RuntimeError):
    """Raised when adapter resources cannot be resolved from a valid root."""


def _with_parents(path: Path) -> Iterable[Path]:
    yield path
    yield from path.parents


def _has_marker(root: Path, required_marker: str) -> bool:
    return (root / required_marker).exists()


def resolve_resource_root(
    *,
    required_marker: str,
    git_common_dir: str | None = None,
    additional_roots: Iterable[Path] = (),
) -> Path:
    """Resolve a repo/resource root that contains the required marker.

    Git common dir is validated instead of trusted because tests may isolate
    database access by mocking it to a temp directory that has no resources.

    Args:
        required_marker: Directory or file that must exist in the root
        git_common_dir: Git common directory path (from GitClient)
        additional_roots: Additional paths to check for root

    Returns:
        Path to the resolved resource root

    Raises:
        ResourceRootNotFoundError: If no root with required_marker is found
    """
    candidates: list[Path] = []
    resolution_errors: list[str] = []

    if git_common_dir:
        from vibe3.utils import (
            RepositoryLayoutError,
            resolve_repo_root_from_common_dir,
        )

        try:
            candidates.append(resolve_repo_root_from_common_dir(git_common_dir))
        except RepositoryLayoutError as exc:
            resolution_errors.append(str(exc))

    candidates.extend(additional_roots)
    candidates.extend(_with_parents(Path.cwd()))

    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if _has_marker(resolved, required_marker):
            return resolved

    details = (
        f"cwd={Path.cwd()}; git_common_dir={git_common_dir or 'unavailable'}; "
        f"required_marker={required_marker}; "
        f"checked_candidates={[str(path) for path in seen]}"
    )
    if resolution_errors:
        details += f"; layout_errors={resolution_errors}"
    raise ResourceRootNotFoundError(f"Cannot resolve resource root; {details}")
