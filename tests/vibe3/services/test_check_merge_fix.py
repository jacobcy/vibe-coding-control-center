"""Tests for CheckService merged PR and auto-fix functionality."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.models.orchestration import IssueState
from vibe3.models.pr import PRResponse, PRState
from vibe3.services.check_cleanup_service import CheckCleanupService
from vibe3.services.check_service import CheckService


@pytest.fixture
def mock_store():
    """Create a mock SQLiteClient."""
    return MagicMock(spec=SQLiteClient)


@pytest.fixture
def mock_git_client():
    """Create a mock GitClient."""
    client = MagicMock(spec=GitClient)
    client.get_current_branch.return_value = "feature/test-branch"
    client._run.return_value = "/path/to/.git"
    return client


@pytest.fixture
def mock_github_client():
    """Create a mock GitHubClient with safe defaults."""
    client = MagicMock(spec=GitHubClient)
    client.list_prs_for_branch.return_value = []
    return client


@pytest.fixture
def check_service(mock_store, mock_git_client, mock_github_client):
    """Create a CheckService instance with mocked dependencies."""
    return CheckService(
        store=mock_store,
        git_client=mock_git_client,
        github_client=mock_github_client,
    )


@pytest.fixture
def cleanup_service(mock_store, mock_git_client):
    """Create a CheckCleanupService instance with mocked dependencies."""
    return CheckCleanupService(
        store=mock_store,
        git_client=mock_git_client,
    )


class TestMergedPRHandling:
    """Tests for merged PR handling."""

    def test_merged_pr_returns_valid(
        self, check_service, mock_store, mock_github_client
    ):
        """Merged PR flow is auto-completed and returns is_valid=True."""
        mock_store.get_flow_state.return_value = {
            "branch": "feature/test-branch",
        }
        mock_store.get_issue_links.return_value = []
        pr = PRResponse(
            number=456,
            title="Test PR",
            body="",
            state=PRState.MERGED,
            head_branch="feature/test-branch",
            base_branch="main",
            url="https://github.com/test/pr/456",
            draft=False,
            merged_at="2026-03-29T00:00:00Z",
        )
        mock_github_client.list_prs_for_branch.return_value = [pr]

        result = check_service.verify_current_flow()

        assert result.is_valid
        assert len(result.issues) == 0
        mock_store.update_flow_state.assert_called_once_with(
            "feature/test-branch", flow_status="done"
        )
        mock_store.add_event.assert_called_once()
        assert mock_store.add_event.call_args[0][1] == "flow_auto_completed"
        # Branch cleanup is now deferred to --clean-branch
        check_service.git_client.delete_branch.assert_not_called()

    def test_missing_local_branch_with_merged_pr_still_marks_done(
        self, check_service, mock_store, mock_github_client
    ):
        """Merged flow converges to done even if local branch is gone."""
        mock_store.get_flow_state.return_value = {
            "branch": "feature/test-branch",
        }
        mock_store.get_issue_links.return_value = []
        check_service.git_client._run.return_value = ""
        pr = PRResponse(
            number=456,
            title="Test PR",
            body="",
            state=PRState.MERGED,
            head_branch="feature/test-branch",
            base_branch="main",
            url="https://github.com/test/pr/456",
            draft=False,
            merged_at="2026-03-29T00:00:00Z",
        )
        mock_github_client.list_prs_for_branch.return_value = [pr]

        result = check_service.verify_current_flow()

        assert result.is_valid
        mock_store.update_flow_state.assert_called_once_with(
            "feature/test-branch", flow_status="done"
        )
        assert mock_store.add_event.call_args[0][1] == "flow_auto_completed"

    def test_merged_cleanup_still_attempts_branch_delete_when_worktree_cleanup_fails(
        self, check_service, mock_store, mock_github_client
    ):
        """Done flow marks status without immediate cleanup (deferred)."""
        mock_store.get_flow_state.return_value = {
            "branch": "feature/test-branch",
        }
        mock_store.get_issue_links.return_value = []
        pr = PRResponse(
            number=456,
            title="Test PR",
            body="",
            state=PRState.MERGED,
            head_branch="feature/test-branch",
            base_branch="main",
            url="https://github.com/test/pr/456",
            draft=False,
            merged_at="2026-03-29T00:00:00Z",
        )
        mock_github_client.list_prs_for_branch.return_value = [pr]
        check_service.git_client.find_worktree_path_for_branch.return_value = "/tmp/wt"

        result = check_service.verify_current_flow()

        assert result.is_valid
        # Branch cleanup is now deferred to --clean-branch
        check_service.git_client.remove_worktree.assert_not_called()
        check_service.git_client.delete_branch.assert_not_called()


class TestStaleFlowHandling:
    """Tests for stale flow handling."""

    def test_ready_empty_auto_scene_is_marked_stale(
        self, check_service, mock_store, mock_github_client
    ):
        """Canonical ready flow with no session/ref/worktree should be auto-staled."""
        mock_store.get_flow_state.return_value = {
            "branch": "task/issue-431",
            "flow_status": "active",
            "task_issue_number": None,
            "manager_session_id": None,
            "planner_session_id": None,
            "executor_session_id": None,
            "reviewer_session_id": None,
            "plan_ref": None,
            "report_ref": None,
            "audit_ref": None,
            "planner_status": None,
            "executor_status": None,
            "reviewer_status": None,
            "execution_pid": None,
            "execution_started_at": None,
            "execution_completed_at": None,
        }
        mock_store.get_issue_links.return_value = []
        mock_github_client.view_issue.return_value = {
            "number": 431,
            "state": "OPEN",
            "labels": [{"name": IssueState.READY.to_label()}],
        }
        mock_github_client.list_prs_for_branch.return_value = []
        with patch.object(
            check_service.git_client,
            "get_current_branch",
            return_value="task/issue-431",
        ):
            with patch.object(
                check_service.git_client,
                "find_worktree_path_for_branch",
                return_value=None,
            ):
                result = check_service.verify_current_flow()

        assert result.is_valid
        mock_store.update_flow_state.assert_called_once_with(
            "task/issue-431", flow_status="stale"
        )
        mock_store.add_event.assert_called_once()
        assert mock_store.add_event.call_args[0][1] == "flow_auto_staled"

    def test_stale_ready_canonical_flow_is_rebuilt_via_flow_manager(
        self, check_service, mock_store, mock_github_client
    ):
        """stale ready canonical flow should be rebuilt through FlowManager."""
        mock_store.get_flow_state.return_value = {
            "branch": "task/issue-431",
            "flow_status": "stale",
            "task_issue_number": None,
        }
        mock_store.get_issue_links.return_value = [
            {"issue_number": 431, "issue_role": "task"}
        ]
        mock_github_client.view_issue.return_value = {
            "number": 431,
            "title": "Rebuild me",
            "state": "OPEN",
            "labels": [{"name": IssueState.READY.to_label()}],
        }
        mock_github_client.list_prs_for_branch.return_value = []

        with patch(
            "vibe3.execution.flow_dispatch.FlowManager.create_flow_for_issue",
            return_value={"branch": "task/issue-431", "flow_status": "active"},
        ) as mock_create_flow:
            with patch.object(
                check_service.git_client,
                "get_current_branch",
                return_value="task/issue-431",
            ):
                result = check_service.verify_current_flow()

        assert result.is_valid
        mock_create_flow.assert_called_once()


class TestAutoFix:
    """Tests for auto_fix method."""

    def test_fix_all_checks_active_and_stale_flows(self, check_service):
        """fix_all should converge stale flows in addition to active flows."""
        from vibe3.commands.check_support import execute_check_mode

        with patch.object(
            check_service, "verify_all_flows", return_value=[]
        ) as mock_verify:
            result = execute_check_mode(check_service, "fix_all")

        assert result.success
        mock_verify.assert_called_once_with(status=["active", "stale"])

    def test_auto_fix_creates_handoff_file(self, check_service, mock_git_client):
        """Test that auto_fix creates missing handoff file."""

        with tempfile.TemporaryDirectory() as tmpdir:
            git_dir = Path(tmpdir) / ".git"
            git_dir.mkdir()

            with patch.object(
                check_service.git_client,
                "get_git_common_dir",
                return_value=str(git_dir),
            ):
                result = check_service.auto_fix(
                    [
                        f"Shared handoff file not found: "
                        f"{git_dir}/vibe3/handoff/x/current.md"
                    ]
                )

        assert result.success

    def test_auto_fix_unfixable_returns_hint(self, check_service):
        """Test that unfixable issues return error with --init hint."""
        result = check_service.auto_fix(["Task issue #123 not found on GitHub"])

        assert not result.success
        assert result.error is not None
        assert "--init" in result.error


class TestCleanResidualBranches:
    """Tests for clean_residual_branches method in CheckCleanupService."""

    def test_clean_residual_branches_removes_done_flow_branches(
        self, cleanup_service, mock_store, mock_git_client
    ):
        """Should clean physical resources for done flows but keep flow record."""
        mock_store.get_all_flows.return_value = [
            {"branch": "feature/done-branch", "flow_status": "done"},
            {"branch": "feature/active-branch", "flow_status": "active"},
        ]
        # Simulate local branch exists for done branch
        mock_git_client._run.return_value = "feature/done-branch"
        mock_git_client.find_worktree_path_for_branch.return_value = None

        result = cleanup_service.clean_residual_branches()

        # Done flow should be in kept_records (physical resources cleaned, record kept)
        assert "feature/done-branch" in result["kept_records"]
        assert len(result["cleaned"]) == 0  # cleaned is for aborted flows only
        assert result["total_flows_checked"] == 1

    def test_clean_residual_branches_skips_when_no_resources(
        self, cleanup_service, mock_store, mock_git_client
    ):
        """Should preserve done/merged flow records even without physical resources.

        Done/merged flows keep their records as completion history.
        Only aborted flows have their records deleted.
        """
        mock_store.get_all_flows.return_value = [
            {"branch": "feature/done-branch", "flow_status": "done"},
        ]
        # Simulate no resources exist
        mock_git_client._run.return_value = ""
        mock_git_client.find_worktree_path_for_branch.return_value = None

        result = cleanup_service.clean_residual_branches()

        # Done flow record should be preserved (in kept_records, not cleaned)
        assert len(result["kept_records"]) == 1
        assert "feature/done-branch" in result["kept_records"]
        assert len(result["cleaned"]) == 0  # cleaned is for aborted flows
        assert result["total_flows_checked"] == 1

    def test_clean_residual_branches_aborted_deletes_record(
        self, cleanup_service, mock_store, mock_git_client
    ):
        """Should delete aborted flow records to allow issue restart."""
        mock_store.get_all_flows.return_value = [
            {"branch": "feature/aborted-branch", "flow_status": "aborted"},
        ]
        # Simulate no resources exist
        mock_git_client._run.return_value = ""
        mock_git_client.find_worktree_path_for_branch.return_value = None

        result = cleanup_service.clean_residual_branches()

        # Aborted flow record should be deleted (in cleaned)
        assert len(result["cleaned"]) == 1
        assert "feature/aborted-branch" in result["cleaned"]
        assert len(result["kept_records"]) == 0  # kept_records is for done/merged
        assert result["total_flows_checked"] == 1

    def test_clean_residual_branches_removes_invalid_records(
        self, cleanup_service, mock_store, mock_git_client
    ):
        """Should remove HEAD records from database."""
        mock_store.get_all_flows.return_value = [
            {"branch": "HEAD", "flow_status": "done"},
            {"branch": "HEAD~1", "flow_status": "aborted"},
        ]

        result = cleanup_service.clean_residual_branches()

        assert len(result["removed_invalid"]) == 2
        assert mock_store.delete_flow.call_count == 2

    def test_clean_residual_branches_handles_partial_failures(
        self, cleanup_service, mock_store, mock_git_client
    ):
        """Should continue cleaning even if some fail."""
        mock_store.get_all_flows.return_value = [
            {"branch": "feature/branch-1", "flow_status": "done"},
            {"branch": "feature/branch-2", "flow_status": "done"},
        ]
        # First branch succeeds, second fails
        call_count = [0]

        def mock_run(cmd):
            call_count[0] += 1
            if call_count[0] <= 1:
                return "feature/branch-1"  # First call for branch-1
            elif call_count[0] <= 2:
                raise RuntimeError("git error")  # First call for branch-2 fails
            return ""  # Subsequent calls

        mock_git_client._run.side_effect = mock_run
        mock_git_client.find_worktree_path_for_branch.return_value = None

        result = cleanup_service.clean_residual_branches()

        # Should have some result despite failures
        assert "failed" in result
        assert result["total_flows_checked"] == 2
