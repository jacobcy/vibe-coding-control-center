# tests/vibe3/clients/test_sqlite_flow_state_repo_validation.py
import sqlite3
import tempfile

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

    def test_accepts_task_branch(self) -> None:
        # Should not raise
        validate_issue_branch_for_role("task/issue-123", "task")

    def test_accepts_dev_branch(self) -> None:
        # Should not raise
        validate_issue_branch_for_role("dev/issue-456", "dev")

    def test_rejects_task_role_with_wrong_prefix(self) -> None:
        with pytest.raises(InvalidBranchLinkError, match="task"):
            validate_issue_branch_for_role("dev/issue-123", "task")


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
