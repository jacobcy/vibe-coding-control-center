"""Generic dispatch-time file loader for governance materials and policies."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Generic, TypeVar

import yaml

from vibe3.prompts import MaterialEntry, PolicyEntry

logger = logging.getLogger(__name__)

T = TypeVar("T")


class FileLoader(Generic[T]):
    """Generic dispatch-time loader that scans a directory for files matching
    given suffixes, applies a parser, and returns typed entries.

    No process-level caching — each call reads from disk (ADR-0003).
    """

    def __init__(
        self,
        base_dir: Path,
        suffixes: tuple[str, ...],
        parser: Callable[[str, Path, str, str, float], T | None],
    ) -> None:
        self._base_dir = base_dir
        self._suffixes = suffixes
        self._parser = parser

    def load_all(self) -> tuple[T, ...]:
        """Load all matching files. Returns empty tuple if dir is missing/empty."""
        if not self._base_dir.exists():
            logger.warning("Directory does not exist: %s", self._base_dir)
            return ()
        if not self._base_dir.is_dir():
            logger.warning("Path is not a directory: %s", self._base_dir)
            return ()

        files: set[Path] = set()
        for suffix in self._suffixes:
            files.update(self._base_dir.glob(f"*{suffix}"))

        entries: list[T] = []
        for file_path in sorted(files, key=lambda p: p.name):
            entry = self.load(file_path.name)
            if entry is not None:
                entries.append(entry)
        return tuple(entries)

    def load(self, name: str) -> T | None:
        """Load a single file by relative name."""
        file_path = self._base_dir / name

        if not file_path.exists():
            return None
        if not file_path.is_file():
            logger.warning("Path is not a file: %s", file_path)
            return None

        try:
            content = file_path.read_text(encoding="utf-8")
            stat = file_path.stat()
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
            return self._parser(
                content, file_path.resolve(), name, content_hash, stat.st_mtime
            )
        except Exception as e:
            logger.warning("Failed to load %s: %s", file_path, e)
            return None


def _parse_material(
    content: str,
    path: Path,
    name: str,
    content_hash: str,
    mtime: float,
) -> MaterialEntry:
    return MaterialEntry(
        path=path,
        name=name,
        content=content,
        content_hash=content_hash,
        mtime=mtime,
    )


def _parse_policy(
    content: str,
    path: Path,
    name: str,
    content_hash: str,
    mtime: float,
) -> PolicyEntry | None:
    data = yaml.safe_load(content)
    if not isinstance(data, dict):
        logger.warning(
            "Policy file %s does not contain a YAML dict, got %s",
            path,
            type(data),
        )
        return None
    return PolicyEntry(
        path=path,
        name=name,
        data=data,
        content_hash=content_hash,
        mtime=mtime,
    )


def material_loader(base_dir: Path) -> FileLoader[MaterialEntry]:
    """Create a loader for governance material files (.md)."""
    return FileLoader(base_dir, suffixes=(".md",), parser=_parse_material)


def policy_loader(base_dir: Path) -> FileLoader[PolicyEntry]:
    """Create a loader for governance policy files (.yaml/.yml)."""
    return FileLoader(base_dir, suffixes=(".yaml", ".yml"), parser=_parse_policy)


def resolve_manager_usernames() -> tuple[str, ...]:
    """Resolve manager usernames from the same config source as ``vibe3 status``."""
    from vibe3.config import get_config_with_env_override, get_manager_usernames

    config = get_config_with_env_override()
    return get_manager_usernames(config.orchestra)
