"""SQLite repository methods for flow state and issue-link persistence."""

import sqlite3
from typing import Any

from loguru import logger

from vibe3.clients.sqlite_base import _HasConnection, _utcnow_iso


class SQLiteFlowStateRepo(_HasConnection):
    """Flow state, issue link, and dependent-scene operations."""

    db_path: str

    VALID_FLOW_STATUSES = {"active", "blocked", "done", "stale"}

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
        "manager_actor",
        "latest_actor",
        "initiated_by",
        "blocked_by_issue",  # NEW: Dependency issue number (INT)
        "blocked_reason",  # Block reason text (TEXT)
        "next_step",
        "flow_status",
        "updated_at",
        "planner_status",
        "executor_status",
        "reviewer_status",
        "execution_pid",
        "execution_started_at",
        "execution_completed_at",
        "latest_verdict",  # Latest verdict record (JSON)
        "transition_count",  # State transition counter for no-op gate
        "deleted_at",  # Soft delete timestamp (ISO 8601 or NULL)
        "worktree_path",  # Canonical worktree path for flow execution
        "noop_gate_github_retry_count",  # GitHub API retry counter
        "noop_gate_malformed_retry_count",  # Malformed response retry counter
    }

    def get_flow_state(self, branch: str) -> dict[str, Any] | None:
        """Get flow state for branch (excludes soft-deleted flows)."""
        conn = self._get_connection()
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

    def get_flow_state_bulk(self, branches: list[str]) -> dict[str, dict[str, Any]]:
        """Batch retrieve flow states for multiple branches (excludes soft-deleted).

        Args:
            branches: List of branch names to query.

        Returns:
            Dict mapping branch -> flow_state dict. Missing branches omitted.
        """
        if not branches:
            return {}
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        placeholders = ",".join("?" for _ in branches)
        cursor.execute(
            f"SELECT * FROM flow_state "
            f"WHERE branch IN ({placeholders}) AND deleted_at IS NULL",
            tuple(branches),
        )
        result: dict[str, dict[str, Any]] = {}
        for row in cursor.fetchall():
            entry = dict(row)
            branch = entry.get("branch")
            if branch:
                result[branch] = entry
        return result

    def update_flow_state(self, branch: str, **kwargs: Any) -> None:
        """Update flow state fields. Raises ValueError for invalid fields."""
        if "updated_at" not in kwargs:
            # Use UTC-aware datetime to ensure timezone consistency
            kwargs["updated_at"] = _utcnow_iso()

        invalid_fields = set(kwargs.keys()) - self.VALID_FLOW_STATE_FIELDS
        if invalid_fields:
            raise ValueError(f"Invalid flow_state fields: {invalid_fields}")

        fields = list(kwargs.keys())
        values = [kwargs[f] for f in fields]
        set_clause = ", ".join([f"{f} = ?" for f in fields])

        conn = self._get_connection()
        with conn:
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
        logger.bind(
            external="sqlite",
            operation="update_flow_state",
            branch=branch,
            fields=fields,
        ).debug("Updated flow state")

    def add_issue_link(self, branch: str, issue_number: int, role: str) -> None:
        # Use UTC-aware datetime for consistency
        now = _utcnow_iso()
        conn = self._get_connection()
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO flow_issue_links "
                "(branch, issue_number, issue_role, created_at) "
                "VALUES (?, ?, ?, ?)",
                (branch, issue_number, role, now),
            )
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
        conn = self._get_connection()
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE flow_issue_links SET issue_role = ? "
                "WHERE branch = ? AND issue_number = ? AND issue_role = ?",
                (new_role, branch, issue_number, old_role),
            )
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
        return bool(updated)

    def get_issue_links(self, branch: str) -> list[dict[str, Any]]:
        conn = self._get_connection()
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

    def get_dependency_links(self, branch: str) -> list[int]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT issue_number FROM flow_issue_links "
            "WHERE branch = ? AND issue_role = 'dependency'",
            (branch,),
        )
        deps = [row[0] for row in cursor.fetchall()]
        logger.bind(
            external="sqlite",
            operation="get_dependency_links",
            branch=branch,
            count=len(deps),
        ).debug("Retrieved dependency links")
        return deps

    def get_task_issue_number(self, branch: str) -> int | None:
        """Get task issue number for a branch from flow_issue_links.

        Args:
            branch: Branch name to query

        Returns:
            Task issue number if found, None otherwise
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT issue_number FROM flow_issue_links "
            "WHERE branch = ? AND issue_role = 'task' LIMIT 1",
            (branch,),
        )
        row = cursor.fetchone()
        result = int(row[0]) if row and row[0] is not None else None
        logger.bind(
            external="sqlite",
            operation="get_task_issue_number",
            branch=branch,
            issue_number=result,
        ).debug("Retrieved task issue number")
        return result

    def get_branch_for_task_issue(self, issue_number: int) -> str | None:
        """Get branch name for a task issue number from flow_issue_links.

        This is the inverse of get_task_issue_number(branch).

        Note: When multiple branches link to the same issue as task,
        this returns an arbitrary one (LIMIT 1). For priority-based
        selection (active canonical → active non-canonical), use
        IssueFlowService.find_active_flow instead.

        Args:
            issue_number: Issue number to query

        Returns:
            Branch name if found, None otherwise
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT branch FROM flow_issue_links "
            "WHERE issue_number = ? AND issue_role = 'task' LIMIT 1",
            (issue_number,),
        )
        row = cursor.fetchone()
        result = row[0] if row and row[0] is not None else None
        logger.bind(
            external="sqlite",
            operation="get_branch_for_task_issue",
            branch=result,
            issue_number=issue_number,
        ).debug("Retrieved branch for task issue")
        return result

    def get_all_flows(self) -> list[dict[str, Any]]:
        """Get all flows (excludes soft-deleted flows)."""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM flow_state WHERE deleted_at IS NULL")
        flows = [dict(row) for row in cursor.fetchall()]
        logger.bind(
            external="sqlite", operation="get_all_flows", count=len(flows)
        ).debug("Retrieved all flows")
        return flows

    def get_flows_by_status(self, status: str) -> list[dict[str, Any]]:
        """Get flows filtered by status (excludes soft-deleted flows).

        Args:
            status: Must be one of 'active', 'blocked', 'done', 'stale'

        Returns:
            List of flow dictionaries matching the status

        Raises:
            ValueError: If status is not a valid flow status value
        """
        if status not in self.VALID_FLOW_STATUSES:
            raise ValueError(
                f"Invalid flow status: {status}. "
                f"Must be one of: {', '.join(sorted(self.VALID_FLOW_STATUSES))}"
            )

        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM flow_state WHERE flow_status = ? AND deleted_at IS NULL",
            (status,),
        )
        flows = [dict(row) for row in cursor.fetchall()]
        logger.bind(
            external="sqlite",
            operation="get_flows_by_status",
            status=status,
            count=len(flows),
        ).debug("Retrieved flows by status")
        return flows

    def get_active_flow_count(self) -> int:
        """Get count of active flows (excludes soft-deleted flows)."""
        conn = self._get_connection()
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
        conn = self._get_connection()
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
        """Soft delete flow and normalize to tombstone state.

        Sets deleted_at timestamp and clears all refs, reasons, actors,
        execution state, and worktree metadata to prevent contradictory state
        where a deleted flow still looks active with populated refs or execution
        status.

        The flow_status is normalized to 'aborted' (terminal state) to
        distinguish tombstones from active flows in audits/debugging.

        Also cascade-deletes non-audit associated records (runtime_session,
        flow_issue_links, flow_context_cache) to prevent zombie state from
        polluting subsequent orchestra dispatch. flow_events is preserved
        as audit trail.
        """
        now = _utcnow_iso()
        conn = self._get_connection()
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE flow_state SET
                    deleted_at = ?,
                    flow_status = 'aborted',
                    spec_ref = NULL,
                    plan_ref = NULL,
                    report_ref = NULL,
                    audit_ref = NULL,
                    indicate_ref = NULL,
                    pr_ref = NULL,
                    blocked_reason = NULL,
                    blocked_by_issue = NULL,
                    blocked_by = NULL,
                    worktree_path = NULL,
                    next_step = NULL,
                    planner_actor = NULL,
                    executor_actor = NULL,
                    reviewer_actor = NULL,
                    manager_actor = NULL,
                    latest_actor = NULL,
                    planner_status = NULL,
                    executor_status = NULL,
                    reviewer_status = NULL,
                    execution_pid = NULL,
                    execution_started_at = NULL,
                    execution_completed_at = NULL,
                    updated_at = ?
                WHERE branch = ?""",
                (now, now, branch),
            )
            cursor.execute("DELETE FROM runtime_session WHERE branch = ?", (branch,))
            cursor.execute("DELETE FROM flow_issue_links WHERE branch = ?", (branch,))
            cursor.execute("DELETE FROM flow_context_cache WHERE branch = ?", (branch,))
        logger.bind(
            external="sqlite",
            operation="soft_delete_flow",
            branch=branch,
        ).info("Soft deleted flow record and normalized to tombstone state")

    def hard_delete_flow(self, branch: str) -> None:
        """Hard delete flow with cascade, removing all related records."""
        conn = self._get_connection()
        with conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM runtime_session WHERE branch = ?", (branch,))
            cursor.execute("DELETE FROM flow_events WHERE branch = ?", (branch,))
            cursor.execute("DELETE FROM flow_issue_links WHERE branch = ?", (branch,))
            cursor.execute("DELETE FROM flow_state WHERE branch = ?", (branch,))
            cursor.execute("DELETE FROM flow_context_cache WHERE branch = ?", (branch,))
        logger.bind(
            external="sqlite",
            operation="hard_delete_flow",
            branch=branch,
        ).info("Hard deleted flow records and cache")

    def delete_flow(self, branch: str, force: bool = False) -> None:
        """Delete flow (soft by default, hard if force=True)."""
        if force:
            self.hard_delete_flow(branch)
        else:
            self.soft_delete_flow(branch)

    def restore_flow(self, branch: str) -> None:
        """Restore soft-deleted or aborted flow by clearing deleted_at and status.

        This method handles two scenarios:
        1. Soft-deleted flows (deleted_at IS NOT NULL, flow_status='aborted')
        2. Aborted flows without tombstone (deleted_at IS NULL, flow_status='aborted')

        In both cases, the flow is restored to active status.
        """
        conn = self._get_connection()
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE flow_state
                   SET deleted_at = NULL, flow_status = 'active'
                   WHERE branch = ?""",
                (branch,),
            )
        logger.bind(
            external="sqlite",
            operation="restore_flow",
            branch=branch,
        ).info("Restored flow to active status")

    def get_deleted_flows(self) -> list[dict[str, Any]]:
        """Get all soft-deleted flows."""
        conn = self._get_connection()
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
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM flow_state WHERE branch = ?", (branch,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

    def get_flows_by_issue(self, issue_number: int, role: str) -> list[dict[str, Any]]:
        """Get flows linked to an issue with specified role (excludes soft-deleted)."""
        conn = self._get_connection()
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

    def get_flows_by_issues_bulk(
        self, issue_numbers: list[int], role: str
    ) -> dict[int, list[dict[str, Any]]]:
        """Batch retrieve flows linked to multiple issues with specified role.

        Args:
            issue_numbers: List of issue numbers to query.
            role: Issue role to filter by (e.g. 'task').

        Returns:
            Dict mapping issue_number -> list of flow dicts (sorted by updated_at DESC).
        """
        if not issue_numbers:
            return {}
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        placeholders = ",".join("?" for _ in issue_numbers)
        cursor.execute(
            f"SELECT l.issue_number, f.* FROM flow_state f "
            f"JOIN flow_issue_links l ON f.branch = l.branch "
            f"WHERE l.issue_number IN ({placeholders}) AND l.issue_role = ? "
            f"AND f.deleted_at IS NULL "
            f"ORDER BY COALESCE(f.updated_at, '') DESC, f.branch ASC",
            (*issue_numbers, role),
        )
        result: dict[int, list[dict[str, Any]]] = {n: [] for n in issue_numbers}
        for row in cursor.fetchall():
            entry = dict(row)
            issue_num = entry.pop("issue_number", None)
            if issue_num is not None and issue_num in result:
                result[issue_num].append(entry)
        return result

    def get_flow_dependents(self, branch: str) -> list[str]:
        """Get dependent flows (excludes soft-deleted flows)."""
        task_issue_number = self.get_task_issue_number(branch)

        if task_issue_number is None:
            logger.bind(
                external="sqlite",
                operation="get_flow_dependents",
                branch=branch,
                dependents_count=0,
            ).debug("No task issue bound; no dependents")
            return []

        conn = self._get_connection()
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
