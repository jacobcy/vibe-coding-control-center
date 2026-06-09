"""Shared hash computation helpers for governance content versioning."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from loguru import logger

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable


@runtime_checkable
class _HashableEntry(Protocol):
    """Protocol for entries with name and content_hash attributes."""

    name: str
    content_hash: str


class _Loadable(Protocol):
    """Protocol for objects with a load_all method."""

    def load_all(self) -> tuple[object, ...]: ...


def compute_governance_hash(entries: Iterable[_HashableEntry]) -> str | None:
    """Compute aggregate SHA-256 hash of governance entries.

    Expects each entry to have ``.name`` and ``.content_hash`` attributes
    (satisfied by PolicyEntry, MaterialEntry, and SimpleNamespace).

    Args:
        entries: Iterable of entries with name and content_hash attributes.

    Returns:
        First 16 hex chars of aggregate SHA-256 hash, or None if empty.
    """
    entry_list = list(entries)
    if not entry_list:
        return None

    hash_parts = sorted(f"{e.name}|{e.content_hash}" for e in entry_list)
    concatenated = "|".join(hash_parts)
    return hashlib.sha256(concatenated.encode("utf-8")).hexdigest()[:16]


def compute_hash_from_loader(
    loader_factory: Callable[[Path], _Loadable],
    base_dir: Path,
) -> str | None:
    """Compute governance hash using a loader factory function.

    Args:
        loader_factory: Callable that accepts a Path and returns a FileLoader.
        base_dir: Directory to scan for governance files.

    Returns:
        Aggregate hash, or None if no entries found or on error.
    """
    try:
        loader = loader_factory(base_dir)
        entries = loader.load_all()
        return compute_governance_hash(entries)  # type: ignore[arg-type]
    except Exception as e:
        logger.warning("Failed to compute governance hash for %s: %s", base_dir, e)
        return None
