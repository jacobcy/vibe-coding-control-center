# tests/vibe3/clients/test_sqlite_flow_state_repo_validation.py
import pytest

from vibe3.clients.sqlite_flow_state_repo import (
    validate_issue_branch_for_role,
)
from vibe3.exceptions import InvalidBranchLinkError


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
