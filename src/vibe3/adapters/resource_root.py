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
    """
    candidates: list[Path] = []

    if git_common_dir:
        candidates.append(Path(git_common_dir).parent)
    else:
        try:
            from vibe3.clients import GitClient

            detected_common_dir = GitClient().get_git_common_dir()
            if detected_common_dir:
                candidates.append(Path(detected_common_dir).parent)
        except Exception:
            pass

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

    raise ResourceRootNotFoundError(
        f"Cannot resolve resource root containing {required_marker!r}"
    )
