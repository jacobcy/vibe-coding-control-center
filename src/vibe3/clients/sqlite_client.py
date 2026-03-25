"""SQLite client for flow state management."""

import datetime
import json
import os
import sqlite3
from typing import Any

from loguru import logger

from vibe3.clients.sqlite_schema import init_schema


class SQLiteClient:
    """SQLite client for managing flow state and events."""

    # Whitelist of valid flow_state columns (security: prevent SQL injection)
    VALID_FLOW_STATE_FIELDS = {
        "branch",
        "flow_slug",
        "task_issue_number",
        "pr_number",
        "spec_ref",
        "plan_ref",
        "report_ref",
        "audit_ref",
        "planner_actor",
        "planner_session_id",
        "executor_actor",
        "executor_session_id",
        "reviewer_actor",
        "reviewer_session_id",
        "latest_actor",
        "blocked_by",
        "next_step",
        "flow_status",
        "updated_at",
        "project_item_id",
        "project_node_id",
    }

    def __init__(self, db_path: str | None = None) -> None:
        if db_path is None:
            git_dir = os.popen("git rev-parse --git-dir").read().strip()
            vibe3_dir = os.path.join(git_dir, "vibe3")
            os.makedirs(vibe3_dir, exist_ok=True)
            db_path = os.path.join(vibe3_dir, "handoff.db")
        self.db_path = db_path
        self._init_db()
        logger.bind(external="sqlite", operation="init", db_path=db_path).debug(
            "SQLite client initialized"
        )

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            init_schema(conn)

    def get_flow_state(self, branch: str) -> dict[str, Any] | None:
        """Get flow state by branch."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM flow_state WHERE branch = ?", (branch,))
            row = cursor.fetchone()
            if row:
                logger.bind(
                    external="sqlite", operation="get_flow_state", branch=branch
                ).debug("Retrieved flow state")
                return dict(row)
            return None

    def update_flow_state(self, branch: str, **kwargs: Any) -> None:
        """Update flow state for branch."""
        if "updated_at" not in kwargs:
            kwargs["updated_at"] = datetime.datetime.now().isoformat()

        # Validate field names against whitelist (prevent SQL injection)
        invalid_fields = set(kwargs.keys()) - self.VALID_FLOW_STATE_FIELDS
        if invalid_fields:
            raise ValueError(f"Invalid flow_state fields: {invalid_fields}")

        fields = list(kwargs.keys())
        values = [kwargs[f] for f in fields]
        set_clause = ", ".join([f"{f} = ?" for f in fields])

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Use branch as slug if not provided (for display fallback)
            flow_slug = kwargs.get("flow_slug", branch.replace("/", "-"))
            cursor.execute(
                "INSERT OR IGNORE INTO flow_state (branch, flow_slug, updated_at) "
                "VALUES (?, ?, ?)",
                (branch, flow_slug, kwargs["updated_at"]),
            )
            cursor.execute(
                f"UPDATE flow_state SET {set_clause} WHERE branch = ?",
                values + [branch],
            )
            conn.commit()
            logger.bind(
                external="sqlite",
                operation="update_flow_state",
                branch=branch,
                fields=fields,
            ).debug("Updated flow state")

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
        branch: str,
        event_type: str | None = None,
        event_type_prefix: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            query = "SELECT * FROM flow_events WHERE branch = ?"
            params: list[Any] = [branch]
            if event_type:
                query += " AND event_type = ?"
                params.append(event_type)
            if event_type_prefix:
                query += " AND event_type LIKE ?"
                params.append(f"{event_type_prefix}%")
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

    def add_issue_link(self, branch: str, issue_number: int, role: str) -> None:
        """Add issue link to flow."""
        now = datetime.datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO flow_issue_links "
                "(branch, issue_number, issue_role, created_at) "
                "VALUES (?, ?, ?, ?)",
                (branch, issue_number, role, now),
            )
            conn.commit()
            logger.bind(
                external="sqlite",
                operation="add_issue_link",
                branch=branch,
                issue=issue_number,
                role=role,
            ).debug("Added issue link")

    def get_issue_links(self, branch: str) -> list[dict[str, Any]]:
        """Get issue links for branch."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM flow_issue_links WHERE branch = ?", (branch,))
            links = [dict(row) for row in cursor.fetchall()]
            logger.bind(
                external="sqlite",
                operation="get_issue_links",
                branch=branch,
                count=len(links),
            ).debug("Retrieved issue links")
            return links

    def get_all_flows(self) -> list[dict[str, Any]]:
        """Get all flows."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM flow_state")
            flows = [dict(row) for row in cursor.fetchall()]
            logger.bind(
                external="sqlite", operation="get_all_flows", count=len(flows)
            ).debug("Retrieved all flows")
            return flows

    def get_flows_by_issue(
        self, issue_number: int, role: str | None = None
    ) -> list[dict[str, Any]]:
        """Get all flows linked to a given issue number."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if role:
                cursor.execute(
                    "SELECT f.* FROM flow_state f "
                    "JOIN flow_issue_links l ON f.branch = l.branch "
                    "WHERE l.issue_number = ? AND l.issue_role = ?",
                    (issue_number, role),
                )
            else:
                cursor.execute(
                    "SELECT f.* FROM flow_state f "
                    "JOIN flow_issue_links l ON f.branch = l.branch "
                    "WHERE l.issue_number = ?",
                    (issue_number,),
                )
            flows = [dict(row) for row in cursor.fetchall()]
            logger.bind(
                external="sqlite",
                operation="get_flows_by_issue",
                issue_number=issue_number,
                role=role,
                count=len(flows),
            ).debug("Retrieved flows by issue")
            return flows

    def update_bridge_fields(
        self,
        branch: str,
        project_item_id: str | None,
        project_node_id: str | None,
    ) -> None:
        """Update task bridge identity fields (project_item_id, project_node_id)."""
        from vibe3.models.task_bridge import TaskBridgeModel

        fields: dict[str, Any] = {}
        if project_item_id is not None:
            fields["project_item_id"] = project_item_id
        if project_node_id is not None:
            fields["project_node_id"] = project_node_id

        TaskBridgeModel.assert_no_truth_write(fields)
        self.update_flow_state(branch, **fields)
        logger.bind(
            external="sqlite", operation="update_bridge_fields", branch=branch
        ).debug("Updated bridge fields")
