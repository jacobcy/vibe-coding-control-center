"""Tests for CheckService."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
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
    """Create a mock GitHubClient."""
    return MagicMock(spec=GitHubClient)


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
            "pr_number": 456,
            "plan_ref": None,
            "report_ref": None,
            "audit_ref": None,
        }
        mock_store.get_issue_links.return_value = [
            {"issue_number": 123, "issue_role": "task"}
        ]
        mock_github_client.view_issue.return_value = {"number": 123}
        mock_github_client.get_pr.return_value = PRResponse(
            number=456,
            title="Test PR",
            body="",
            state=PRState.OPEN,
            head_branch="feature/test-branch",
            base_branch="main",
            url="https://github.com/test/pr/456",
            draft=False,
        )

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
            "task_issue_number": 123,
        }
        mock_store.get_issue_links.return_value = []
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
        """Test PR does not match branch."""
        mock_store.get_flow_state.return_value = {
            "branch": "feature/test-branch",
            "pr_number": 456,
        }
        mock_store.get_issue_links.return_value = []
        mock_github_client.get_pr.return_value = PRResponse(
            number=456,
            title="Test PR",
            body="",
            state=PRState.OPEN,
            head_branch="other-branch",
            base_branch="main",
            url="https://github.com/test/pr/456",
            draft=False,
        )

        result = check_service.verify_current_flow()

        assert not result.is_valid
        assert "PR #456 does not match branch" in result.issues[0]

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
        }
        mock_store.get_issue_links.return_value = []

        with tempfile.TemporaryDirectory() as tmpdir:
            git_dir = Path(tmpdir) / ".git"
            git_dir.mkdir()
            # Don't create handoff file

            with patch.object(
                check_service.git_client,
                "get_git_common_dir",
                return_value=str(git_dir),
            ):
                result = check_service.verify_current_flow()

        assert not result.is_valid
        assert any("Shared handoff file not found" in issue for issue in result.issues)

    def test_merged_pr_returns_valid(
        self, check_service, mock_store, mock_github_client
    ):
        """Merged PR flow is auto-completed and returns is_valid=True."""
        mock_store.get_flow_state.return_value = {
            "branch": "feature/test-branch",
            "pr_number": 456,
        }
        mock_store.get_issue_links.return_value = []
        mock_github_client.get_pr.return_value = PRResponse(
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

        result = check_service.verify_current_flow()

        assert result.is_valid
        assert len(result.issues) == 0
        mock_store.update_flow_state.assert_called_once_with(
            "feature/test-branch", flow_status="done"
        )
        mock_store.add_event.assert_called_once()
        assert mock_store.add_event.call_args[0][1] == "flow_auto_completed"


class TestAutoFix:
    """Tests for auto_fix method."""

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
