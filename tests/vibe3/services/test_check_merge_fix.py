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
        check_service.git_client.delete_branch.assert_called_once_with(
            "feature/test-branch",
            force=True,
            skip_if_worktree=True,
        )

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
        """Done convergence tries branch cleanup if worktree removal fails."""
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
        check_service.git_client.remove_worktree.side_effect = RuntimeError("bad wt")

        result = check_service.verify_current_flow()

        assert result.is_valid
        check_service.git_client.remove_worktree.assert_called_once_with(
            "/tmp/wt", force=True
        )
        check_service.git_client.delete_branch.assert_called_once_with(
            "feature/test-branch",
            force=True,
            skip_if_worktree=True,
        )


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
        with patch.object(
            check_service, "verify_all_flows", return_value=[]
        ) as mock_verify:
            result = check_service.execute_check("fix_all")

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
