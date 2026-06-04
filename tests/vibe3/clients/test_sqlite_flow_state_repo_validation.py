# tests/vibe3/clients/test_sqlite_flow_state_repo_validation.py
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from vibe3.clients.sqlite_base import _get_global_connection
from vibe3.clients.sqlite_flow_state_repo import (
    SQLiteFlowStateRepo,
    validate_issue_branch_for_role,
)
from vibe3.clients.sqlite_schema import init_schema
from vibe3.exceptions import InvalidBranchLinkError


class TestRepo(SQLiteFlowStateRepo):
    """Test helper that provides db_path and _get_connection for testing."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        conn = _get_global_connection(db_path)
        init_schema(conn)

    def _get_connection(self) -> sqlite3.Connection:
        return _get_global_connection(self.db_path)


class TestValidateIssueBranchForRole:
    def test_rejects_main_branch(self) -> None:
        with pytest.raises(InvalidBranchLinkError, match="main"):
            validate_issue_branch_for_role("main", "task")

    def test_rejects_master_branch(self) -> None:
        with pytest.raises(InvalidBranchLinkError, match="master"):
            validate_issue_branch_for_role("master", "task")

    def test_rejects_develop_branch(self) -> None:
        with pytest.raises(InvalidBranchLinkError, match="develop"):
            validate_issue_branch_for_role("develop", "dev")

    def test_rejects_origin_main_branch(self) -> None:
        with pytest.raises(InvalidBranchLinkError, match="origin/main"):
            validate_issue_branch_for_role("origin/main", "task")

    def test_rejects_upstream_develop_branch(self) -> None:
        with pytest.raises(InvalidBranchLinkError, match="upstream/develop"):
            validate_issue_branch_for_role("upstream/develop", "dev")

    def test_accepts_task_branch(self) -> None:
        # Should not raise
        validate_issue_branch_for_role("task/issue-123", "task")

    def test_accepts_dev_branch(self) -> None:
        # Should not raise
        validate_issue_branch_for_role("dev/issue-456", "dev")

    def test_accepts_dependency_role_with_task_branch(self) -> None:
        # Should not raise
        validate_issue_branch_for_role("task/issue-789", "dependency")

    def test_accepts_dependency_role_with_dev_branch(self) -> None:
        # Should not raise
        validate_issue_branch_for_role("dev/issue-100", "dependency")

    def test_rejects_dependency_role_with_main_branch(self) -> None:
        with pytest.raises(InvalidBranchLinkError, match="main"):
            validate_issue_branch_for_role("main", "dependency")

    def test_rejects_task_role_with_wrong_prefix(self) -> None:
        with pytest.raises(InvalidBranchLinkError, match="task"):
            validate_issue_branch_for_role("dev/issue-123", "task")

    def test_rejects_dependency_role_with_wrong_prefix(self) -> None:
        with pytest.raises(InvalidBranchLinkError, match="dependency"):
            validate_issue_branch_for_role("feature/abc", "dependency")


class TestAddIssueLinkValidation:
    def test_add_issue_link_rejects_main_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            repo = TestRepo(db_path=db_path)

            with pytest.raises(InvalidBranchLinkError, match="main"):
                repo.add_issue_link("main", 123, "task")

    def test_add_issue_link_accepts_valid_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            repo = TestRepo(db_path=db_path)

            # Should not raise
            repo.add_issue_link("task/issue-123", 123, "task")

            # Verify link was added
            links = repo.get_issue_links("task/issue-123")
            assert len(links) == 1
            assert links[0]["issue_number"] == 123


class TestGetFlowsByIssueValidation:
    def test_get_flows_by_issue_detects_invalid_branch(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        repo = TestRepo(db_path=str(db_path))

        # Manually insert invalid data (simulating existing pollution)
        # Need both flow_state and flow_issue_links records
        conn = repo._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO flow_state
            (branch, flow_slug, updated_at)
            VALUES (?, ?, ?)
            """,
            ("main", "main", datetime.now(timezone.utc).isoformat()),
        )
        cursor.execute(
            """
            INSERT INTO flow_issue_links
            (branch, issue_number, issue_role, created_at)
            VALUES (?, ?, ?, ?)
            """,
            ("main", 999, "task", datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()

        # Should raise when detecting invalid branch
        with pytest.raises(InvalidBranchLinkError, match="main"):
            repo.get_flows_by_issue(999, "task")

    def test_get_flows_by_issue_accepts_valid_branches(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        repo = TestRepo(db_path=str(db_path))

        # Insert valid data (both flow_state and flow_issue_links)
        conn = repo._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO flow_state
            (branch, flow_slug, updated_at)
            VALUES (?, ?, ?)
            """,
            (
                "task/issue-888",
                "task-issue-888",
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()

        repo.add_issue_link("task/issue-888", 888, "task")

        # Should not raise
        flows = repo.get_flows_by_issue(888, "task")
        assert len(flows) == 1
        assert flows[0]["branch"] == "task/issue-888"
