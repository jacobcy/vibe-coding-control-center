"""SQLite client for flow state management."""

import datetime
import os
import sqlite3
from typing import Any

from loguru import logger


class SQLiteClient:
    """SQLite client for managing flow state and events."""

    def __init__(self, db_path: str | None = None) -> None:
        """Initialize SQLite client.

        Args:
            db_path: Path to database file. If None, uses .git/vibe3/handoff.db
        """
        if db_path is None:
            # Use git rev-parse --git-dir to find the correct directory
            git_dir = os.popen("git rev-parse --git-dir").read().strip()
            vibe3_dir = os.path.join(git_dir, "vibe3")
            if not os.path.exists(vibe3_dir):
                os.makedirs(vibe3_dir, exist_ok=True)
            db_path = os.path.join(vibe3_dir, "handoff.db")

        self.db_path = db_path
        self._init_db()
        logger.bind(
            external="sqlite",
            operation="init",
            db_path=db_path,
        ).debug("SQLite client initialized")

    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # schema_meta
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

            # flow_state
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS flow_state (
                    branch TEXT PRIMARY KEY,
                    flow_slug TEXT NOT NULL,
                    task_issue_number INTEGER,
                    pr_number INTEGER,
                    spec_ref TEXT,
                    plan_ref TEXT,
                    report_ref TEXT,
                    audit_ref TEXT,
                    planner_actor TEXT,
                    planner_session_id TEXT,
                    executor_actor TEXT,
                    executor_session_id TEXT,
                    reviewer_actor TEXT,
                    reviewer_session_id TEXT,
                    latest_actor TEXT,
                    blocked_by TEXT,
                    next_step TEXT,
                    flow_status TEXT NOT NULL DEFAULT 'active',
                    updated_at TEXT NOT NULL
                )
            """)

            # flow_issue_links
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS flow_issue_links (
                    branch TEXT NOT NULL,
                    issue_number INTEGER NOT NULL,
                    issue_role TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (branch, issue_number, issue_role)
                )
            """)

            # Unique index for task issue
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_flow_single_task_issue
                ON flow_issue_links(branch)
                WHERE issue_role = 'task'
            """)

            # flow_events
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS flow_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    branch TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    detail TEXT,
                    created_at TEXT NOT NULL
                )
            """)

            # Set schema version if not set
            cursor.execute(
                "INSERT OR IGNORE INTO schema_meta (key, value) "
                "VALUES ('schema_version', 'v3')"
            )
            cursor.execute(
                "INSERT OR IGNORE INTO schema_meta (key, value) "
                "VALUES ('store_type', 'handoff_store')"
            )
            conn.commit()
            logger.bind(external="sqlite", operation="init_schema").debug(
                "Database schema initialized"
            )

    def get_flow_state(self, branch: str) -> dict[str, Any] | None:
        """Get flow state by branch.

        Args:
            branch: Git branch name

        Returns:
            Flow state dict or None if not found
        """
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
            logger.bind(
                external="sqlite", operation="get_flow_state", branch=branch
            ).debug("No flow state found")
            return None

    def update_flow_state(self, branch: str, **kwargs: Any) -> None:
        """Update flow state for branch.

        Args:
            branch: Git branch name
            **kwargs: Fields to update
        """
        if "updated_at" not in kwargs:
            kwargs["updated_at"] = datetime.datetime.now().isoformat()

        fields = list(kwargs.keys())
        values = [kwargs[f] for f in fields]

        set_clause = ", ".join([f"{f} = ?" for f in fields])

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Ensure the row exists
            cursor.execute(
                "INSERT OR IGNORE INTO flow_state (branch, flow_slug, updated_at) "
                "VALUES (?, ?, ?)",
                (branch, kwargs.get("flow_slug", "unknown"), kwargs["updated_at"]),
            )

            query = f"UPDATE flow_state SET {set_clause} WHERE branch = ?"
            cursor.execute(query, values + [branch])
            conn.commit()
            logger.bind(
                external="sqlite",
                operation="update_flow_state",
                branch=branch,
                fields=fields,
            ).debug("Updated flow state")

    def add_event(
        self, branch: str, event_type: str, actor: str, detail: str | None = None
    ) -> None:
        """Add event to flow.

        Args:
            branch: Git branch name
            event_type: Type of event
            actor: Actor who performed the event
            detail: Optional event detail
        """
        now = datetime.datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO flow_events (branch, event_type, actor, detail, created_at)
                VALUES (?, ?, ?, ?, ?)
            """,
                (branch, event_type, actor, detail, now),
            )
            conn.commit()
            logger.bind(
                external="sqlite",
                operation="add_event",
                branch=branch,
                event_type=event_type,
            ).debug("Added event")

    def add_issue_link(self, branch: str, issue_number: int, role: str) -> None:
        """Add issue link to flow.

        Args:
            branch: Git branch name
            issue_number: GitHub issue number
            role: Issue role (e.g., 'task', 'blocks')
        """
        now = datetime.datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO flow_issue_links
                    (branch, issue_number, issue_role, created_at)
                VALUES (?, ?, ?, ?)
            """,
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
        """Get issue links for branch.

        Args:
            branch: Git branch name

        Returns:
            List of issue link dicts
        """
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

    def get_active_flows(self) -> list[dict[str, Any]]:
        """Get all active flows.

        Returns:
            List of active flow state dicts
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM flow_state WHERE flow_status = 'active'")
            flows = [dict(row) for row in cursor.fetchall()]
            logger.bind(
                external="sqlite", operation="get_active_flows", count=len(flows)
            ).debug("Retrieved active flows")
            return flows

    def get_all_flows(self) -> list[dict[str, Any]]:
        """Get all flows.

        Returns:
            List of all flow state dicts
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM flow_state")
            flows = [dict(row) for row in cursor.fetchall()]
            logger.bind(
                external="sqlite", operation="get_all_flows", count=len(flows)
            ).debug("Retrieved all flows")
            return flows
