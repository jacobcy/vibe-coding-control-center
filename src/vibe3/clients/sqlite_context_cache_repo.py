"""SQLite repository methods for flow context cache persistence."""

import datetime
from typing import Any

from loguru import logger

from vibe3.clients.sqlite_base import _HasConnection


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
        updated_at = datetime.datetime.now().isoformat()
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
