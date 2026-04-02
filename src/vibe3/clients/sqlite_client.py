"""SQLite client for flow state management."""

import datetime
import json
import sqlite3
from pathlib import Path
from typing import Any

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.clients.sqlite_schema import init_schema
from vibe3.exceptions import GitError


class SQLiteClient:
    """SQLite client for managing flow state and events."""

    # Whitelist of valid flow_state columns (security: prevent SQL injection)
    VALID_FLOW_STATE_FIELDS = {
        "branch",
        "flow_slug",
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
        "initiated_by",
        "blocked_by",
        "next_step",
        "flow_status",
        "updated_at",
        "project_item_id",
        "project_node_id",
        "planner_status",
        "executor_status",
        "reviewer_status",
        "execution_pid",
        "execution_started_at",
        "execution_completed_at",
    }

    def __init__(self, db_path: str | None = None) -> None:
        if db_path is None:
            # Use git common dir to ensure shared state across worktrees
            git_common_dir = GitClient().get_git_common_dir()
            if not git_common_dir:
                raise GitError("rev-parse --git-common-dir", "returned empty path")

            git_dir = Path(git_common_dir)
            if not git_dir.is_absolute():
                raise GitError(
                    "rev-parse --git-common-dir",
                    f"returned non-absolute path: {git_dir}",
                )
            vibe3_dir = git_dir / "vibe3"
            vibe3_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(vibe3_dir / "handoff.db")
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
        branch: str | None = None,
        event_type: str | None = None,
        event_type_prefix: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Get flow events.

        Args:
            branch: Filter by branch name. Pass None to query all branches.
            event_type: Filter by exact event type.
            event_type_prefix: Filter by event type prefix.
            limit: Max number of results.
            offset: Pagination offset.
        """
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

    def get_active_flow_count(self) -> int:
        """Get count of active flows."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM flow_state WHERE flow_status = 'active'"
            )
            count = cursor.fetchone()[0]
            logger.bind(
                external="sqlite", operation="get_active_flow_count", count=count
            ).debug("Retrieved active flow count")
            return int(count)

    def get_flows_by_issue(self, issue_number: int, role: str) -> list[dict[str, Any]]:
        """Get all flows linked to a given issue number."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT f.* FROM flow_state f "
                "JOIN flow_issue_links l ON f.branch = l.branch "
                "WHERE l.issue_number = ? AND l.issue_role = ?",
                (issue_number, role),
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

    def get_flow_dependents(self, branch: str) -> list[str]:
        """Get branches that depend on the given branch.

        Args:
            branch: Branch name to check dependents for

        Returns:
            List of branch names that depend on this branch (only active flows)

        Example:
            >>> store = SQLiteClient()
            >>> dependents = store.get_flow_dependents("feature/A")
            >>> # ["feature/B"] or ["feature/B", "feature/C"]
        """
        # Resolve primary task issue from flow_issue_links (truth-first)
        task_issue_number: int | None = None
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT issue_number
                FROM flow_issue_links
                WHERE branch = ? AND issue_role = 'task'
                LIMIT 1
                """,
                (branch,),
            )
            row = cursor.fetchone()
            if row and row[0] is not None:
                task_issue_number = int(row[0])

        if task_issue_number is None:
            logger.bind(
                external="sqlite",
                operation="get_flow_dependents",
                branch=branch,
                dependents_count=0,
            ).debug("No task issue bound; no dependents")
            return []

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT DISTINCT fil.branch
                FROM flow_issue_links fil
                JOIN flow_state fs ON fil.branch = fs.branch
                WHERE fil.issue_number = ?
                  AND fil.issue_role = 'dependency'
                  AND fs.flow_status = 'active'
                ORDER BY fil.branch
                """,
                (task_issue_number,),
            )
            dependents = [row[0] for row in cursor.fetchall()]
            logger.bind(
                external="sqlite",
                operation="get_flow_dependents",
                branch=branch,
                dependents_count=len(dependents),
            ).debug("Retrieved flow dependents")
            return dependents
