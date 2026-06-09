"""Persistent cache for recent PR status snapshots.

This cache stores the most recent batch-scanned PR facts from GitHub so that
multiple command paths can share one local view instead of each querying `gh`
independently. It is intentionally branch-oriented because most callers need
`branch -> PR status` resolution.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from vibe3.services import get_vibe3_cache_path


class RecentPRCache:
    """Persistent cache for recent PR status by branch."""

    def __init__(self, repo_path: Path) -> None:
        self.repo_path = repo_path
        self.cache_file = get_vibe3_cache_path(repo_path, "recent_prs.json")

    def _ensure_dir(self) -> None:
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_cache(self) -> dict[str, Any]:
        try:
            with open(self.cache_file, encoding="utf-8") as f:
                data = json.load(f)
                if (
                    isinstance(data, dict)
                    and isinstance(data.get("prs"), dict)
                    and "last_sync" in data
                ):
                    return data
        except FileNotFoundError:
            logger.bind(domain="recent_pr_cache").debug(
                "Cache file not found, starting fresh"
            )
        except json.JSONDecodeError as exc:
            logger.bind(domain="recent_pr_cache", error=str(exc)).warning(
                "Cache file corrupted, starting fresh"
            )

        return {"last_sync": None, "prs": {}}

    def _save_cache(self, data: dict[str, Any]) -> None:
        """Save cache atomically using temp file + rename.

        This prevents cache corruption if the process is interrupted mid-write
        or if multiple commands write concurrently.
        """
        self._ensure_dir()
        # Write to temp file in the same directory
        temp_fd, temp_path = tempfile.mkstemp(
            dir=self.cache_file.parent,
            prefix=".recent_prs.tmp.",
            suffix=".json",
        )
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            # Atomic rename (POSIX) or replace (cross-platform fallback)
            Path(temp_path).replace(self.cache_file)
        except Exception:
            # Clean up temp file on error
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

    def is_fresh(self, max_age_minutes: int = 10) -> bool:
        """Whether the recent PR snapshot is still fresh enough to reuse."""
        cache = self._load_cache()
        last_sync = cache.get("last_sync")
        if not isinstance(last_sync, str) or not last_sync:
            return False

        try:
            parsed = datetime.fromisoformat(last_sync)
        except ValueError:
            return False

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)
        return parsed >= cutoff

    def get_all_branch_prs(self) -> dict[str, dict[str, Any]]:
        """Return cached branch -> PR dict mapping."""
        cache = self._load_cache()
        prs = cache.get("prs", {})
        return prs if isinstance(prs, dict) else {}

    def get_branch_pr(self, branch: str) -> dict[str, Any] | None:
        """Return cached PR entry for a branch, if present."""
        return self.get_all_branch_prs().get(branch)

    def sync(self, github_client: Any, limit: int = 50) -> int:
        """Replace cache with latest recent PR snapshot from GitHub."""
        logger.bind(domain="recent_pr_cache", limit=limit).info(
            "Syncing recent PR cache"
        )
        prs = github_client.list_all_prs(state="all", limit=limit)
        branch_map: dict[str, dict[str, Any]] = {}
        for pr in prs:
            branch = getattr(pr, "head_branch", None)
            if not isinstance(branch, str) or not branch:
                continue
            merged_at = getattr(pr, "merged_at", None)
            closed_at = getattr(pr, "closed_at", None)
            branch_map[branch] = {
                "number": getattr(pr, "number", None),
                "title": getattr(pr, "title", ""),
                "state": getattr(getattr(pr, "state", None), "value", None),
                "draft": bool(getattr(pr, "draft", False)),
                "url": getattr(pr, "url", ""),
                "head_branch": branch,
                "base_branch": getattr(pr, "base_branch", "main"),
                "merged_at": (
                    merged_at.isoformat()
                    if isinstance(merged_at, datetime)
                    else merged_at
                ),
                "closed_at": (
                    closed_at.isoformat()
                    if isinstance(closed_at, datetime)
                    else closed_at
                ),
            }

        self._save_cache(
            {
                "last_sync": datetime.now(timezone.utc).isoformat(),
                "prs": branch_map,
            }
        )
        return len(branch_map)

    def upsert_branch_pr(self, branch: str, pr_data: dict[str, Any]) -> None:
        """Upsert a single branch PR entry without forcing full resync."""
        cache = self._load_cache()
        prs = cache.get("prs", {})
        if not isinstance(prs, dict):
            prs = {}
        prs[branch] = pr_data
        cache["prs"] = prs
        self._save_cache(cache)
