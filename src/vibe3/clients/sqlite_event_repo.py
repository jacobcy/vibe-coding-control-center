"""SQLite repository methods for flow event persistence."""

import datetime
import json
import sqlite3
from typing import Any

from loguru import logger


class SQLiteEventRepo:
    """Flow event read/write operations."""

    db_path: str

    def add_event(
        self,
        branch: str,
        event_type: str,
        actor: str,
        detail: str | None = None,
        refs: dict[str, Any] | None = None,
    ) -> None:
        now = datetime.datetime.now().isoformat()
        refs_json = json.dumps(refs) if refs else None
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO flow_events "
                "(branch, event_type, actor, detail, refs, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (branch, event_type, actor, detail, refs_json, now),
            )
            conn.commit()
            logger.bind(
                external="sqlite",
                operation="add_event",
                branch=branch,
                event_type=event_type,
            ).debug("Added event")

    def get_events(
        self,
        branch: str | None = None,
        event_type: str | None = None,
        event_type_prefix: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Get flow events."""
        normalized_branch = branch
        if isinstance(normalized_branch, str) and not normalized_branch.strip():
            normalized_branch = None

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            conditions: list[str] = []
            params: list[Any] = []
            if normalized_branch is not None:
                conditions.append("branch = ?")
                params.append(normalized_branch)
            if event_type:
                conditions.append("event_type = ?")
                params.append(event_type)
            if event_type_prefix:
                conditions.append("event_type LIKE ?")
                params.append(f"{event_type_prefix}%")
            query = "SELECT * FROM flow_events"
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY created_at DESC"
            if limit is not None:
                query += " LIMIT ? OFFSET ?"
                params.extend([limit, offset])
            cursor.execute(query, params)
            rows = [dict(row) for row in cursor.fetchall()]
            for row in rows:
                if row.get("refs"):
                    try:
                        row["refs"] = json.loads(row["refs"])
                    except json.JSONDecodeError:
                        row["refs"] = None
                else:
                    row["refs"] = None
            return rows
