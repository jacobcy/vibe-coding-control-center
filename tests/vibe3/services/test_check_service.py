"""Tests for CheckService."""

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


class TestVerifyCurrentFlow:
    """Tests for verify_current_flow method."""

    def test_verify_flow_valid(self, check_service, mock_store, mock_github_client):
        """Test valid flow passes all checks."""
        # Setup mock data
        mock_store.get_flow_state.return_value = {
            "branch": "feature/test-branch",
            "task_issue_number": 123,
            "plan_ref": None,
            "report_ref": None,
            "audit_ref": None,
        }
        mock_store.get_issue_links.return_value = [
            {"issue_number": 123, "issue_role": "task"}
        ]
        mock_github_client.view_issue.return_value = {"number": 123}
        pr = PRResponse(
            number=456,
            title="Test PR",
            body="",
            state=PRState.OPEN,
            head_branch="feature/test-branch",
            base_branch="main",
            url="https://github.com/test/pr/456",
            draft=False,
        )
        mock_github_client.list_prs_for_branch.return_value = [pr]

        with tempfile.TemporaryDirectory() as tmpdir:
            git_dir = Path(tmpdir) / ".git"
            git_dir.mkdir()
            # Calculate hash suffix to match check_service logic
            import hashlib

            branch_hash = hashlib.sha256(b"feature/test-branch").hexdigest()[:8]
            handoff_dir = (
                git_dir / "vibe3" / "handoff" / f"feature-test-branch-{branch_hash}"
            )
            handoff_dir.mkdir(parents=True)
            (handoff_dir / "current.md").write_text("# Handoff")

            with patch.object(
                check_service.git_client,
                "get_git_common_dir",
                return_value=str(git_dir),
            ):
                result = check_service.verify_current_flow()

        assert result.is_valid
        assert len(result.issues) == 0

    def test_verify_flow_missing(self, check_service, mock_store):
        """Test flow not found."""
        mock_store.get_flow_state.return_value = None

        result = check_service.verify_current_flow()

        assert not result.is_valid
        assert "No flow record for branch" in result.issues[0]

    def test_verify_task_issue_missing(
        self, check_service, mock_store, mock_github_client
    ):
        """Test task issue not found on GitHub."""
        mock_store.get_flow_state.return_value = {
            "branch": "feature/test-branch",
        }
        mock_store.get_issue_links.return_value = [
            {"issue_number": 123, "issue_role": "task"}
        ]
        mock_github_client.view_issue.return_value = None

        result = check_service.verify_current_flow()

        assert not result.is_valid
        assert "Task issue #123 not found on GitHub" in result.issues

    def test_verify_multiple_task_issues(self, check_service, mock_store):
        """Test multiple task issues for branch."""
        mock_store.get_flow_state.return_value = {
            "branch": "feature/test-branch",
        }
        mock_store.get_issue_links.return_value = [
            {"issue_number": 123, "issue_role": "task"},
            {"issue_number": 456, "issue_role": "task"},
        ]

        result = check_service.verify_current_flow()

        assert not result.is_valid
        assert "Multiple task issues" in result.issues[0]

    def test_verify_pr_mismatch(self, check_service, mock_store, mock_github_client):
        """Test PR mismatch (e.g. branch has no PR on GitHub)."""
        mock_store.get_flow_state.return_value = {
            "branch": "feature/test-branch",
        }
        mock_store.get_issue_links.return_value = []
        # GitHub returns nothing for this branch
        mock_github_client.list_prs_for_branch.return_value = []

        with tempfile.TemporaryDirectory() as tmpdir:
            git_dir = Path(tmpdir) / ".git"
            git_dir.mkdir()
            import hashlib

            branch_hash = hashlib.sha256(b"feature/test-branch").hexdigest()[:8]
            handoff_dir = (
                git_dir / "vibe3" / "handoff" / f"feature-test-branch-{branch_hash}"
            )
            handoff_dir.mkdir(parents=True)
            (handoff_dir / "current.md").write_text("# Handoff")

            with patch.object(
                check_service.git_client,
                "get_git_common_dir",
                return_value=str(git_dir),
            ):
                result = check_service.verify_current_flow()

        # In remote-first, having no PR is not necessarily an error.
        # But for now, let's just ensure it doesn't crash and we handle it.
        # If the test expected "PR #456 does not match branch", we adjust it
        # because we no longer have pr_number in flow_data.
        assert result.is_valid
        assert len(result.issues) == 0

    def test_verify_ref_files_missing(self, check_service, mock_store):
        """Test ref files not found."""
        mock_store.get_flow_state.return_value = {
            "branch": "feature/test-branch",
            "plan_ref": "docs/plans/missing.md",
        }
        mock_store.get_issue_links.return_value = []

        result = check_service.verify_current_flow()

        assert not result.is_valid
        assert any("plan_ref file not found" in issue for issue in result.issues)

    def test_verify_current_handoff_missing(self, check_service, mock_store):
        """Test shared handoff file missing."""
        mock_store.get_flow_state.return_value = {
            "branch": "feature/test-branch",
            "task_issue_number": 123,
        }
        mock_store.get_issue_links.return_value = [
            {"issue_number": 123, "issue_role": "task"}
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            git_dir = Path(tmpdir) / ".git"
            git_dir.mkdir()
            # Don't create handoff file

            with patch.object(
                check_service.github_client,
                "view_issue",
                return_value={
                    "number": 123,
                    "state": "OPEN",
                    "labels": [{"name": "state/handoff"}],
                },
            ):
                with patch.object(
                    check_service.git_client,
                    "get_git_common_dir",
                    return_value=str(git_dir),
                ):
                    result = check_service.verify_current_flow()

        assert not result.is_valid
        assert any("Shared handoff file not found" in issue for issue in result.issues)

    def test_verify_ready_issue_does_not_require_handoff(
        self, check_service, mock_store, mock_github_client
    ):
        """Ready issues should not fail just because current.md is missing."""
        mock_store.get_flow_state.return_value = {
            "branch": "feature/test-branch",
            "task_issue_number": 123,
        }
        mock_store.get_issue_links.return_value = [
            {"issue_number": 123, "issue_role": "task"}
        ]
        mock_github_client.view_issue.return_value = {
            "number": 123,
            "state": "OPEN",
            "labels": [{"name": "state/ready"}],
        }
        mock_github_client.list_prs_for_branch.return_value = []

        result = check_service.verify_current_flow()

        assert result.is_valid
        assert not any(
            "Shared handoff file not found" in issue for issue in result.issues
        )

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
            "vibe3.manager.flow_manager.FlowManager.create_flow_for_issue",
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
        import tempfile

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
