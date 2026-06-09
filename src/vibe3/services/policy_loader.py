"""Dispatch-time loader for governance policy files (.yaml)."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import yaml

from vibe3.prompts.models import PolicyEntry

logger = logging.getLogger(__name__)


class PolicyLoader:
    """Dispatch-time loader for governance policy files (.yaml).

    Scans a directory for YAML policy files, parses them,
    and computes stable content hashes.
    """

    def __init__(self, base_dir: Path) -> None:
        """Initialize the loader with a base directory.

        Args:
            base_dir: Directory to scan for .yaml/.yml files.
        """
        self._base_dir = base_dir

    def load_all(self) -> tuple[PolicyEntry, ...]:
        """Load all .yaml/.yml files from the base directory.

        Returns empty tuple if directory doesn't exist or has no YAML files.
        """
        if not self._base_dir.exists():
            logger.warning(f"Policy directory does not exist: {self._base_dir}")
            return ()

        if not self._base_dir.is_dir():
            logger.warning(f"Policy path is not a directory: {self._base_dir}")
            return ()

        entries: list[PolicyEntry] = []
        for yaml_file in sorted(self._base_dir.glob("*.yaml")):
            entry = self.load(yaml_file.name)
            if entry is not None:
                entries.append(entry)

        # Also check for .yml files
        for yaml_file in sorted(self._base_dir.glob("*.yml")):
            entry = self.load(yaml_file.name)
            if entry is not None:
                entries.append(entry)

        # Sort by name to ensure deterministic ordering
        entries.sort(key=lambda e: e.name)
        return tuple(entries)

    def load(self, name: str) -> PolicyEntry | None:
        """Load a single policy by relative name.

        Args:
            name: Relative filename (e.g., "autoharness.yaml").

        Returns:
            PolicyEntry if file exists and is valid YAML, None otherwise.
        """
        file_path = self._base_dir / name

        if not file_path.exists():
            return None

        if not file_path.is_file():
            logger.warning(f"Policy path is not a file: {file_path}")
            return None

        try:
            content = file_path.read_text(encoding="utf-8")
            data = yaml.safe_load(content)

            if not isinstance(data, dict):
                logger.warning(
                    f"Policy file {file_path} does not contain a "
                    f"YAML dict, got {type(data)}"
                )
                return None

            stat = file_path.stat()
            content_hash = self._compute_hash(content)

            return PolicyEntry(
                path=file_path.resolve(),
                name=name,
                data=data,
                content_hash=content_hash,
                mtime=stat.st_mtime,
            )
        except yaml.YAMLError as e:
            logger.warning(f"Failed to parse YAML policy {file_path}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Failed to load policy {file_path}: {e}")
            return None

    def _compute_hash(self, content: str) -> str:
        """SHA-256 hash of content, truncated to 16 hex chars."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def resolve_manager_usernames() -> tuple[str, ...]:
    """Resolve manager usernames from the same config source as `vibe3 status`.

    Delegates to vibe3.config.manager_config.get_manager_usernames
    with the current orchestra config. This ensures runtime material loading
    sees the same manager usernames as the status command.
    """
    from vibe3.config import get_config_with_env_override, get_manager_usernames

    config = get_config_with_env_override()
    return get_manager_usernames(config.orchestra)
