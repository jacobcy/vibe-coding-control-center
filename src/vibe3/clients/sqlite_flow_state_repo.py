"""SQLite repository methods for flow state and issue-link persistence."""

import datetime
import sqlite3
from typing import Any

from loguru import logger


class SQLiteFlowStateRepo:
    """Flow state, issue link, and dependent-scene operations."""

    db_path: str

    VALID_FLOW_STATE_FIELDS = {
        "branch",
        "flow_slug",
        "spec_ref",
        "plan_ref",
        "report_ref",
        "audit_ref",
        "indicate_ref",
        "pr_ref",  # PR URL as proof of PR creation
        "planner_actor",
        "executor_actor",
        "reviewer_actor",
        "latest_actor",
        "initiated_by",
        "blocked_by",  # Legacy field (deprecated, kept for backward compatibility)
        "blocked_by_issue",  # NEW: Dependency issue number (INT)
        "blocked_reason",  # NEW: Block reason text (TEXT)
        "failed_reason",  # NEW: Fail reason text (TEXT)
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
        "latest_verdict",  # Latest verdict record (JSON)
        "deleted_at",  # Soft delete timestamp (ISO 8601 or NULL)
    }

    def get_flow_state(self, branch: str) -> dict[str, Any] | None:
        """Get flow state for branch (excludes soft-deleted flows)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM flow_state WHERE branch = ? AND deleted_at IS NULL",
                (branch,),
            )
            row = cursor.fetchone()
            if row:
                logger.bind(
                    external="sqlite", operation="get_flow_state", branch=branch
                ).debug("Retrieved flow state")
                return dict(row)
            return None

    def update_flow_state(self, branch: str, **kwargs: Any) -> None:
        """Update flow state fields.

        Validation is handled at the service layer (FlowStateService).

        Raises:
            ValueError: If invalid fields are provided
        """
        if "updated_at" not in kwargs:
            kwargs["updated_at"] = datetime.datetime.now().isoformat()

        invalid_fields = set(kwargs.keys()) - self.VALID_FLOW_STATE_FIELDS
        if invalid_fields:
            raise ValueError(f"Invalid flow_state fields: {invalid_fields}")

        fields = list(kwargs.keys())
        values = [kwargs[f] for f in fields]
        set_clause = ", ".join([f"{f} = ?" for f in fields])

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
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

    def add_issue_link(self, branch: str, issue_number: int, role: str) -> None:
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

    def update_issue_link_role(
        self,
        branch: str,
        issue_number: int,
        old_role: str,
        new_role: str,
    ) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE flow_issue_links SET issue_role = ? "
                "WHERE branch = ? AND issue_number = ? AND issue_role = ?",
                (new_role, branch, issue_number, old_role),
            )
            conn.commit()
            updated = cursor.rowcount > 0
            logger.bind(
                external="sqlite",
                operation="update_issue_link_role",
                branch=branch,
                issue=issue_number,
                old_role=old_role,
                new_role=new_role,
                updated=updated,
            ).debug("Updated issue link role")
            return updated

    def get_issue_links(self, branch: str) -> list[dict[str, Any]]:
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
        """Get all flows (excludes soft-deleted flows)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM flow_state WHERE deleted_at IS NULL")
            flows = [dict(row) for row in cursor.fetchall()]
            logger.bind(
                external="sqlite", operation="get_all_flows", count=len(flows)
            ).debug("Retrieved all flows")
            return flows

    def get_active_flow_count(self) -> int:
        """Get count of active flows (excludes soft-deleted flows)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM flow_state "
                "WHERE flow_status = 'active' AND deleted_at IS NULL"
            )
            count = cursor.fetchone()[0]
            logger.bind(
                external="sqlite", operation="get_active_flow_count", count=count
            ).debug("Retrieved active flow count")
            return int(count)

    def get_active_auto_flow_count(self) -> int:
        """Get count of active auto flows (excludes soft-deleted flows)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM flow_state "
                "WHERE flow_status = 'active' AND branch LIKE 'task/issue-%' "
                "AND deleted_at IS NULL"
            )
            count = cursor.fetchone()[0]
            logger.bind(
                external="sqlite",
                operation="get_active_auto_flow_count",
                count=count,
            ).debug("Retrieved active auto flow count")
            return int(count)

    def soft_delete_flow(self, branch: str) -> None:
        """Soft delete flow by setting deleted_at timestamp.

        Preserves all flow data for audit trail and potential recovery.
        """
        now = datetime.datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE flow_state SET deleted_at = ? WHERE branch = ?",
                (now, branch),
            )
            conn.commit()
        logger.bind(
            external="sqlite",
            operation="soft_delete_flow",
            branch=branch,
        ).info("Soft deleted flow record")

    def hard_delete_flow(self, branch: str) -> None:
        """Hard delete flow with cascade (physical deletion).

        Removes all flow records including runtime_session, events,
        issue_links, and context cache.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM runtime_session WHERE branch = ?", (branch,))
            cursor.execute("DELETE FROM flow_events WHERE branch = ?", (branch,))
            cursor.execute("DELETE FROM flow_issue_links WHERE branch = ?", (branch,))
            cursor.execute("DELETE FROM flow_state WHERE branch = ?", (branch,))
            cursor.execute("DELETE FROM flow_context_cache WHERE branch = ?", (branch,))
            conn.commit()
        logger.bind(
            external="sqlite",
            operation="hard_delete_flow",
            branch=branch,
        ).info("Hard deleted flow records and cache")

    def delete_flow(self, branch: str, force: bool = False) -> None:
        """Delete flow (soft by default, hard if force=True).

        Args:
            branch: Branch name
            force: If True, perform hard delete; otherwise soft delete
        """
        if force:
            self.hard_delete_flow(branch)
        else:
            self.soft_delete_flow(branch)

    def restore_flow(self, branch: str) -> None:
        """Restore soft-deleted flow by clearing deleted_at."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE flow_state SET deleted_at = NULL WHERE branch = ?",
                (branch,),
            )
            conn.commit()
        logger.bind(
            external="sqlite",
            operation="restore_flow",
            branch=branch,
        ).info("Restored soft-deleted flow")

    def get_deleted_flows(self) -> list[dict[str, Any]]:
        """Get all soft-deleted flows."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM flow_state WHERE deleted_at IS NOT NULL "
                "ORDER BY deleted_at DESC"
            )
            flows = [dict(row) for row in cursor.fetchall()]
            logger.bind(
                external="sqlite", operation="get_deleted_flows", count=len(flows)
            ).debug("Retrieved deleted flows")
            return flows

    def get_flow_state_include_deleted(self, branch: str) -> dict[str, Any] | None:
        """Get flow state including soft-deleted flows (for recovery check)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM flow_state WHERE branch = ?", (branch,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def get_flows_by_issue(self, issue_number: int, role: str) -> list[dict[str, Any]]:
        """Get flows linked to an issue with specified role (excludes soft-deleted).

        Returns flows ordered by updated_at DESC, branch ASC for stable sorting.
        Domain-specific priority logic (canonical/active) should be implemented
        at the service layer, not here.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT f.* FROM flow_state f "
                "JOIN flow_issue_links l ON f.branch = l.branch "
                "WHERE l.issue_number = ? AND l.issue_role = ? "
                "AND f.deleted_at IS NULL "
                "ORDER BY COALESCE(f.updated_at, '') DESC, f.branch ASC",
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
        """Get dependent flows (excludes soft-deleted flows)."""
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
                  AND fs.deleted_at IS NULL
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
