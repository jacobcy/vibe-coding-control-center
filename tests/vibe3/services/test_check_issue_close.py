"""Tests for issue auto-close behavior in _mark_flow_done.

Tests cover:
- Idempotent close (already closed vs freshly closed)
- Multi-flow binding protection
- Role filtering (task vs related vs dependency)
- Non-task branch auto-close (extension beyond task/issue-N)
"""

from unittest.mock import MagicMock

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.services.check_service import CheckService


class TestMarkFlowDoneIssueClose:
    """Test _mark_flow_done issue closing behavior."""

    def test_mark_flow_done_closes_task_issue(self, tmp_path):
        """Single active flow, task issue open → issue closed."""
        # ARRANGE
        store = SQLiteClient(db_path=tmp_path / "test.db")
        branch = "task/issue-123"
        issue_number = 123

        store.update_flow_state(branch, flow_status="active")
        store.add_issue_link(branch, issue_number, role="task")

        git_client = MagicMock(spec=GitClient)
        git_client.get_git_common_dir.return_value = tmp_path

        github_client = MagicMock(spec=GitHubClient)
        github_client.close_issue_if_open.return_value = "closed"
        github_client.view_issue.return_value = {
            "state": "open",
            "number": issue_number,
        }

        # Create handoff file
        from vibe3.utils.git_helpers import get_branch_handoff_dir

        handoff_dir = get_branch_handoff_dir(tmp_path, branch)
        handoff_dir.mkdir(parents=True, exist_ok=True)
        (handoff_dir / "current.md").touch()

        service = CheckService(
            store=store, git_client=git_client, github_client=github_client
        )

        # ACT
        suggestions = service._mark_flow_done(branch, "PR merged")

        # ASSERT
        assert suggestions["issue_to_close"] == issue_number
        github_client.close_issue_if_open.assert_called_once_with(
            issue_number=issue_number,
            closing_comment=(
                "PR merged. Flow 'task/issue-123' completed. "
                "Closed automatically by vibe check."
            ),
        )

        flow = store.get_flow_state(branch)
        assert flow["flow_status"] == "done"

    def test_mark_flow_done_already_closed_idempotent(self, tmp_path):
        """Issue already closed → returns 'already_closed', no close call made."""
        # ARRANGE
        store = SQLiteClient(db_path=tmp_path / "test.db")
        branch = "task/issue-123"
        issue_number = 123

        store.update_flow_state(branch, flow_status="active")
        store.add_issue_link(branch, issue_number, role="task")

        git_client = MagicMock(spec=GitClient)
        git_client.get_git_common_dir.return_value = tmp_path

        github_client = MagicMock(spec=GitHubClient)
        # close_issue_if_open returns "already_closed" when issue is already closed
        github_client.close_issue_if_open.return_value = "already_closed"

        service = CheckService(
            store=store, git_client=git_client, github_client=github_client
        )

        # ACT
        suggestions = service._mark_flow_done(branch, "PR merged")

        # ASSERT: suggestions should NOT have issue_to_close since it was already closed
        assert suggestions["issue_to_close"] is None
        github_client.close_issue_if_open.assert_called_once()

    def test_mark_flow_done_skips_close_when_other_active_flows(self, tmp_path):
        """Same issue has another active flow → issue NOT closed."""
        # ARRANGE
        store = SQLiteClient(db_path=tmp_path / "test.db")
        issue_number = 123

        # Current branch being marked done
        branch_done = "task/issue-123"
        store.update_flow_state(branch_done, flow_status="active")
        store.add_issue_link(branch_done, issue_number, role="task")

        # Another active flow for the same issue
        branch_active = "dev/issue-123"
        store.update_flow_state(branch_active, flow_status="active")
        store.add_issue_link(branch_active, issue_number, role="task")

        git_client = MagicMock(spec=GitClient)
        git_client.get_git_common_dir.return_value = tmp_path

        github_client = MagicMock(spec=GitHubClient)
        github_client.close_issue_if_open.return_value = "closed"

        service = CheckService(
            store=store, git_client=git_client, github_client=github_client
        )

        # ACT
        suggestions = service._mark_flow_done(branch_done, "PR merged")

        # ASSERT: Issue should NOT be closed because other active flow exists
        assert suggestions["issue_to_close"] is None
        # close_issue_if_open should NOT be called
        github_client.close_issue_if_open.assert_not_called()

    def test_mark_flow_done_closes_when_other_flows_are_done(self, tmp_path):
        """Other flows done/stale/aborted → issue closed (only active flows block)."""
        # ARRANGE
        store = SQLiteClient(db_path=tmp_path / "test.db")
        issue_number = 123

        # Current branch being marked done
        branch_done = "task/issue-123"
        store.update_flow_state(branch_done, flow_status="active")
        store.add_issue_link(branch_done, issue_number, role="task")

        # Another flow for the same issue, but already done
        branch_done2 = "dev/issue-123"
        store.update_flow_state(branch_done2, flow_status="done")
        store.add_issue_link(branch_done2, issue_number, role="task")

        git_client = MagicMock(spec=GitClient)
        git_client.get_git_common_dir.return_value = tmp_path

        github_client = MagicMock(spec=GitHubClient)
        github_client.close_issue_if_open.return_value = "closed"

        service = CheckService(
            store=store, git_client=git_client, github_client=github_client
        )

        # ACT
        suggestions = service._mark_flow_done(branch_done, "PR merged")

        # ASSERT: Issue SHOULD be closed because no other ACTIVE flows
        assert suggestions["issue_to_close"] == issue_number
        github_client.close_issue_if_open.assert_called_once()

    def test_mark_flow_done_ignores_related_issue(self, tmp_path):
        """Flow has role=related link → related issue NOT closed."""
        # ARRANGE
        store = SQLiteClient(db_path=tmp_path / "test.db")
        branch = "task/issue-456"

        store.update_flow_state(branch, flow_status="active")
        # Link with role=related (NOT role=task)
        store.add_issue_link(branch, 456, role="related")

        git_client = MagicMock(spec=GitClient)
        git_client.get_git_common_dir.return_value = tmp_path

        github_client = MagicMock(spec=GitHubClient)

        service = CheckService(
            store=store, git_client=git_client, github_client=github_client
        )

        # ACT
        suggestions = service._mark_flow_done(branch, "PR merged")

        # ASSERT: Issue should NOT be closed because role is "related" not "task"
        assert suggestions["issue_to_close"] is None
        github_client.close_issue_if_open.assert_not_called()

    def test_mark_flow_done_ignores_dependency_issue(self, tmp_path):
        """Flow has role=dependency link → dependency issue NOT closed."""
        # ARRANGE
        store = SQLiteClient(db_path=tmp_path / "test.db")
        branch = "task/issue-789"

        store.update_flow_state(branch, flow_status="active")
        # Link with role=dependency (NOT role=task)
        store.add_issue_link(branch, 789, role="dependency")

        git_client = MagicMock(spec=GitClient)
        git_client.get_git_common_dir.return_value = tmp_path

        github_client = MagicMock(spec=GitHubClient)

        service = CheckService(
            store=store, git_client=git_client, github_client=github_client
        )

        # ACT
        suggestions = service._mark_flow_done(branch, "PR merged")

        # ASSERT: Issue should NOT be closed because role is "dependency" not "task"
        assert suggestions["issue_to_close"] is None
        github_client.close_issue_if_open.assert_not_called()

    def test_mark_flow_done_non_task_branch_closes_issue(self, tmp_path):
        """Branch dev/issue-123 with task issue → issue closed (no branch check)."""
        # ARRANGE
        store = SQLiteClient(db_path=tmp_path / "test.db")
        branch = "dev/issue-123"  # Non-canonical branch name
        issue_number = 123

        store.update_flow_state(branch, flow_status="active")
        store.add_issue_link(branch, issue_number, role="task")

        git_client = MagicMock(spec=GitClient)
        git_client.get_git_common_dir.return_value = tmp_path

        github_client = MagicMock(spec=GitHubClient)
        github_client.close_issue_if_open.return_value = "closed"

        service = CheckService(
            store=store, git_client=git_client, github_client=github_client
        )

        # ACT
        suggestions = service._mark_flow_done(branch, "PR merged")

        # ASSERT: Issue SHOULD be closed even though branch is not task/issue-N
        assert suggestions["issue_to_close"] == issue_number
        github_client.close_issue_if_open.assert_called_once()

    def test_mark_flow_done_no_task_issue_succeeds(self, tmp_path):
        """Flow has no task issue → no close attempt, flow marked done."""
        # ARRANGE
        store = SQLiteClient(db_path=tmp_path / "test.db")
        branch = "task/feature-xyz"

        store.update_flow_state(branch, flow_status="active")
        # No issue links

        git_client = MagicMock(spec=GitClient)
        git_client.get_git_common_dir.return_value = tmp_path

        github_client = MagicMock(spec=GitHubClient)

        service = CheckService(
            store=store, git_client=git_client, github_client=github_client
        )

        # ACT
        suggestions = service._mark_flow_done(branch, "PR merged")

        # ASSERT: Flow marked done, no issue close attempted
        assert suggestions["issue_to_close"] is None
        github_client.close_issue_if_open.assert_not_called()

        flow = store.get_flow_state(branch)
        assert flow["flow_status"] == "done"

    def test_mark_flow_done_multiple_task_issues_closes_one(self, tmp_path):
        """Flow has multiple task issues → closes one of them."""
        # ARRANGE
        store = SQLiteClient(db_path=tmp_path / "test.db")
        branch = "task/issue-multi"

        store.update_flow_state(branch, flow_status="active")
        store.add_issue_link(branch, 111, role="task")
        store.add_issue_link(branch, 222, role="task")

        git_client = MagicMock(spec=GitClient)
        git_client.get_git_common_dir.return_value = tmp_path

        github_client = MagicMock(spec=GitHubClient)
        github_client.close_issue_if_open.return_value = "closed"

        service = CheckService(
            store=store, git_client=git_client, github_client=github_client
        )

        # ACT
        suggestions = service._mark_flow_done(branch, "PR merged")

        # ASSERT: One of the task issues should be closed (order depends on SQLite)
        assert suggestions["issue_to_close"] in (111, 222)
        github_client.close_issue_if_open.assert_called_once()
