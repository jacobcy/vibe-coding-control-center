"""Asset synchronization service."""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger


@dataclass
class SyncResult:
    """Result of asset sync operation."""

    copied: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


class AssetSync:
    """Synchronize builtin assets to global directory."""

    def __init__(
        self,
        builtin_dir: Path,
        global_dir: Path,
    ):
        """Initialize sync service.

        Args:
            builtin_dir: Source directory with builtin assets
            global_dir: Target directory for global assets
        """
        self.builtin_dir = builtin_dir
        self.global_dir = global_dir

    def run(self) -> SyncResult:
        """Execute sync operation.

        Copies builtin assets to global directory, skipping files
        with identical checksums.
        """
        result = SyncResult()

        if not self.builtin_dir.exists():
            logger.bind(domain="assets", action="sync").warning(
                f"Builtin assets directory not found: {self.builtin_dir}"
            )
            return result

        for source_file in self.builtin_dir.rglob("*"):
            if not source_file.is_file():
                continue

            relative_path = source_file.relative_to(self.builtin_dir)
            target_file = self.global_dir / relative_path

            # Check if file exists with same checksum
            if target_file.exists():
                source_checksum = self._sha256(source_file)
                target_checksum = self._sha256(target_file)

                if source_checksum == target_checksum:
                    logger.bind(
                        domain="assets",
                        action="sync",
                        path=str(relative_path),
                    ).debug("Skipping identical file")
                    result.skipped += 1
                    continue

            # Copy file
            try:
                target_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_file, target_file)
                logger.bind(
                    domain="assets",
                    action="sync",
                    path=str(relative_path),
                ).info("Copied asset")
                result.copied += 1
            except (OSError, shutil.Error) as exc:
                logger.bind(
                    domain="assets",
                    action="sync",
                    path=str(relative_path),
                ).error(f"Failed to copy: {exc}")
                result.errors.append(str(relative_path))

        # Generate manifest
        self._generate_manifest()

        return result

    def _sha256(self, path: Path) -> str:
        """Calculate SHA256 checksum of file."""
        sha256_hash = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

    def _generate_manifest(self) -> None:
        """Generate manifest.json with checksums."""
        from vibe3.assets.manifest import AssetManifest

        checksums: dict[str, str] = {}

        if self.global_dir.exists():
            for file_path in self.global_dir.rglob("*"):
                if file_path.is_file():
                    relative = file_path.relative_to(self.global_dir)
                    checksums[str(relative)] = self._sha256(file_path)

        manifest = AssetManifest(
            version="1.0.0",
            checksums=checksums,
        )

        manifest_path = self.global_dir / "manifest.json"
        manifest.save(manifest_path)

        logger.bind(domain="assets", action="sync").info(
            f"Generated manifest with {len(checksums)} entries"
        )
