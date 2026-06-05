"""SQLite repository methods for flow context cache persistence."""

from typing import Any

from loguru import logger

from vibe3.clients.sqlite_base import _HasConnection, _utcnow_iso


class SQLiteContextCacheRepo(_HasConnection):
    """Flow context cache operations."""

    db_path: str

    def upsert_flow_context_cache(
        self,
        branch: str,
        task_issue_number: int | None,
        issue_title: str | None,
        pr_number: int | None,
        pr_title: str | None,
    ) -> None:
        updated_at = _utcnow_iso()
        conn = self._get_connection()
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO flow_context_cache
                    (branch, task_issue_number, issue_title,
                     pr_number, pr_title, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    branch,
                    task_issue_number,
                    issue_title,
                    pr_number,
                    pr_title,
                    updated_at,
                ),
            )
        logger.bind(
            external="sqlite",
            operation="upsert_flow_context_cache",
            branch=branch,
        ).debug("Upserted flow context cache")

    def get_flow_context_cache(self, branch: str) -> dict[str, Any] | None:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM flow_context_cache WHERE branch = ?", (branch,))
        row = cursor.fetchone()
        if row:
            # Convert row to dict using cursor.description (thread-safe)
            columns = [col[0] for col in cursor.description]
            result = dict(zip(columns, row))
            logger.bind(
                external="sqlite",
                operation="get_flow_context_cache",
                branch=branch,
            ).debug("Retrieved flow context cache")
            return result
        return None

    def get_flow_context_cache_bulk(
        self, branches: list[str]
    ) -> dict[str, dict[str, Any]]:
        """Batch retrieve flow context cache entries for multiple branches.

        Args:
            branches: List of branch names to fetch.

        Returns:
            Dict mapping branch -> cache entry. Missing branches are omitted.
        """
        if not branches:
            return {}
        conn = self._get_connection()
        cursor = conn.cursor()
        placeholders = ",".join("?" for _ in branches)
        cursor.execute(
            f"SELECT * FROM flow_context_cache WHERE branch IN ({placeholders})",
            tuple(branches),
        )
        columns = [col[0] for col in cursor.description]
        result: dict[str, dict[str, Any]] = {}
        for row in cursor.fetchall():
            entry = dict(zip(columns, row))
            branch = entry.get("branch")
            if branch:
                result[branch] = entry
        return result

    def delete_flow_context_cache(self, branch: str) -> None:
        conn = self._get_connection()
        with conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM flow_context_cache WHERE branch = ?", (branch,))
        logger.bind(
            external="sqlite",
            operation="delete_flow_context_cache",
            branch=branch,
        ).debug("Deleted flow context cache")

    def upsert_flow_context_cache_bulk(
        self,
        entries: list[tuple[str, int | None, str | None, int | None, str | None]],
    ) -> None:
        """Bulk upsert flow context cache entries in a single transaction.

        Args:
            entries: List of (branch, task_issue_number, issue_title,
                     pr_number, pr_title) tuples.
        """
        if not entries:
            return

        updated_at = _utcnow_iso()
        conn = self._get_connection()
        with conn:
            cursor = conn.cursor()
            rows = [(b, tin, it, pn, pt, updated_at) for b, tin, it, pn, pt in entries]
            cursor.executemany(
                """
                INSERT OR REPLACE INTO flow_context_cache
                    (branch, task_issue_number, issue_title,
                     pr_number, pr_title, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        logger.bind(
            external="sqlite",
            operation="upsert_flow_context_cache_bulk",
            count=len(entries),
        ).debug("Bulk upserted flow context cache")
