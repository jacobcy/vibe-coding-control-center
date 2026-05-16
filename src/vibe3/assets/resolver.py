"""Asset resolver with layered lookup."""

from __future__ import annotations

from pathlib import Path

from loguru import logger


class AssetResolver:
    """Resolve assets with layered priority: repo-local → global → builtin."""

    def __init__(self, global_dir: Path | None = None):
        """Initialize resolver with optional global directory override."""
        from vibe3.assets.constants import ASSETS_DIR

        self.global_dir = global_dir or ASSETS_DIR

    def resolve(
        self,
        relative_path: str,
        repo_root: Path | None = None,
    ) -> Path | None:
        """Resolve asset path with layered lookup.

        Priority order:
        1. repo-local explicit path
        2. repo-local .vibe/ overlay
        3. user-global ~/.vibe/assets
        4. package builtin fallback

        Returns None if not found in any layer.
        """
        # Layer 1 & 2: repo-local
        if repo_root:
            repo_local = repo_root / relative_path
            if repo_local.exists():
                logger.bind(
                    domain="assets",
                    action="resolve",
                    path=relative_path,
                    layer="repo-local",
                ).debug("Asset resolved from repo-local")
                return repo_local

            repo_overlay = repo_root / ".vibe" / relative_path
            if repo_overlay.exists():
                logger.bind(
                    domain="assets",
                    action="resolve",
                    path=relative_path,
                    layer="repo-overlay",
                ).debug("Asset resolved from repo overlay")
                return repo_overlay

        # Layer 3: global assets
        global_path = self.global_dir / relative_path
        if global_path.exists():
            logger.bind(
                domain="assets",
                action="resolve",
                path=relative_path,
                layer="global",
            ).debug("Asset resolved from global assets")
            return global_path

        # Layer 4: builtin fallback (handled by caller)
        logger.bind(
            domain="assets",
            action="resolve",
            path=relative_path,
            layer="not-found",
        ).debug("Asset not found in any layer")

        return None

    def resolve_with_provenance(
        self,
        relative_path: str,
        repo_root: Path | None = None,
    ) -> tuple[Path, str] | None:
        """Resolve asset and return provenance information.

        Returns tuple of (path, layer_name) or None if not found.
        """
        # Layer 1 & 2: repo-local
        if repo_root:
            repo_local = repo_root / relative_path
            if repo_local.exists():
                return (repo_local, "repo-local")

            repo_overlay = repo_root / ".vibe" / relative_path
            if repo_overlay.exists():
                return (repo_overlay, "repo-overlay")

        # Layer 3: global
        global_path = self.global_dir / relative_path
        if global_path.exists():
            return (global_path, "global")

        return None
