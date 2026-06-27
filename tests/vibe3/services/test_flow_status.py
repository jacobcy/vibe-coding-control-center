"""Tests for flow status and listing."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.clients import GitClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.models.data_source import DataSource
from vibe3.services.flow.service import FlowService
from vibe3.services.flow.status_resolver import FlowStatusResolver


@pytest.fixture
def mock_store():
    """Mock SQLite client."""
    return MagicMock()


@pytest.fixture
def mock_git():
    """Mock git client."""
    return MagicMock()


class TestFlowStatus:
    """Tests for individual flow status."""

    def test_get_flow_status_success(self, mock_store, mock_git) -> None:
        """Test getting flow status successfully."""
        mock_store.get_flow_state.return_value = {
            "branch": "test-branch",
            "flow_slug": "test-slug",
            "flow_status": "active",
            "updated_at": "2026-03-16T00:00:00",
        }
        mock_store.get_issue_links.return_value = [
            {
                "branch": "test-branch",
                "issue_number": 476,
                "issue_role": "task",
                "created_at": "2026-03-16T00:00:00",
            }
        ]

        service = FlowService(store=mock_store, git_client=mock_git)
        # PRService is imported inside get_flow_status, need to patch it
        with patch("vibe3.services.pr.service.PRService") as mock_pr_class:
            mock_pr_svc = mock_pr_class.return_value
            mock_pr_result = MagicMock(number=42, is_ready=True)
            mock_pr_svc.get_branch_pr_status.return_value = mock_pr_result

            mock_git.find_worktree_path_for_branch.return_value = Path(
                "/path/to/worktree"
            )

            result = service.get_flow_status("test-branch")

        assert result is not None
        assert result.branch == "test-branch"
        assert result.flow_status == "active"
        # Verify hydrated fields
        assert result.pr_number == 42
        assert result.pr_ready_for_review is True
        assert result.worktree_root == "/path/to/worktree"
        assert result.task_issue_number == 476
        assert len(result.issues) == 1
        assert result.issues[0].issue_number == 476

    def test_get_flow_status_not_found(self, mock_store, mock_git) -> None:
        """Test getting flow status for non-existent branch."""
        mock_store.get_flow_state.return_value = None

        service = FlowService(store=mock_store, git_client=mock_git)
        result = service.get_flow_status("non-existent")

        assert result is None

    def test_get_flow_status_no_pr_no_worktree(self, mock_store, mock_git) -> None:
        """Test flow status when no PR exists and no worktree found."""
        mock_store.get_flow_state.return_value = {
            "branch": "test-branch",
            "flow_slug": "test-slug",
            "flow_status": "active",
            "updated_at": "2026-03-16T00:00:00",
        }
        mock_store.get_issue_links.return_value = []

        service = FlowService(store=mock_store, git_client=mock_git)
        with patch("vibe3.services.pr.service.PRService") as mock_pr_class:
            mock_pr_svc = mock_pr_class.return_value
            mock_pr_svc.get_branch_pr_status.return_value = None

            mock_git.find_worktree_path_for_branch.return_value = None

            result = service.get_flow_status("test-branch")

        assert result is not None
        assert result.branch == "test-branch"
        assert result.pr_number is None
        assert result.pr_ready_for_review is False
        assert result.worktree_root is None
        assert result.task_issue_number is None

    def test_get_flow_status_pr_hydration_failure(self, mock_store, mock_git) -> None:
        """Test flow status gracefully handles PR hydration failure."""
        mock_store.get_flow_state.return_value = {
            "branch": "test-branch",
            "flow_slug": "test-slug",
            "flow_status": "active",
            "updated_at": "2026-03-16T00:00:00",
        }
        mock_store.get_issue_links.return_value = []

        service = FlowService(store=mock_store, git_client=mock_git)
        with patch("vibe3.services.pr.service.PRService") as mock_pr_class:
            mock_pr_svc = mock_pr_class.return_value
            mock_pr_svc.get_branch_pr_status.side_effect = Exception("GitHub down")
            mock_git.find_worktree_path_for_branch.return_value = None

            result = service.get_flow_status("test-branch")

        assert result is not None
        assert result.branch == "test-branch"
        assert result.flow_status == "active"
        # PR hydration failure should result in default values
        assert result.pr_number is None
        assert result.pr_ready_for_review is False
        assert result.worktree_root is None

    def test_get_flow_status_task_issue_number_resolution(
        self, mock_store, mock_git
    ) -> None:
        """Test task_issue_number is correctly resolved from issue links."""
        mock_store.get_flow_state.return_value = {
            "branch": "test-branch",
            "flow_slug": "test-slug",
            "flow_status": "active",
            "updated_at": "2026-03-16T00:00:00",
        }
        mock_store.get_issue_links.return_value = [
            {
                "branch": "test-branch",
                "issue_number": 100,
                "issue_role": "related",
                "created_at": "2026-03-16T00:00:00",
            },
            {
                "branch": "test-branch",
                "issue_number": 200,
                "issue_role": "task",
                "created_at": "2026-03-16T00:00:00",
            },
        ]

        service = FlowService(store=mock_store, git_client=mock_git)
        with patch("vibe3.services.pr.service.PRService") as mock_pr_class:
            mock_pr_svc = mock_pr_class.return_value
            mock_pr_svc.get_branch_pr_status.return_value = None

            mock_git.find_worktree_path_for_branch.return_value = None

            result = service.get_flow_status("test-branch")

        assert result is not None
        # Only task-role issue should be resolved
        assert result.task_issue_number == 200
        assert len(result.issues) == 2
        assert result.issues[0].issue_number == 100
        assert result.issues[1].issue_number == 200


class TestDoneEligibility:
    """Tests for terminal-flow delivery confirmation."""

    def test_pr_ref_without_merged_pr_is_not_delivery_confirmation(self) -> None:
        """A PR reference proves creation, not merge delivery."""
        from vibe3.services.flow.status import FlowStatusService

        github = MagicMock()
        github.list_prs_for_branch.return_value = []
        service = FlowStatusService(
            store=MagicMock(),
            git_client=MagicMock(),
            github_client=github,
        )
        flow_state = {
            "planner_status": "done",
            "executor_status": "done",
            "reviewer_status": "done",
            "pr_ref": "https://github.com/example/repo/pull/99",
            "pr_number": 99,
        }

        result = service.evaluate_aborted_to_done_eligibility(
            flow_state,
            "task/issue-99",
        )

        assert result == (False, None)
        github.list_prs_for_branch.assert_called_once_with("task/issue-99")

    def test_remote_merged_pr_confirms_delivery(self) -> None:
        """A merged PR discovered by branch confirms delivery."""
        from vibe3.services.flow.status import FlowStatusService

        merged_pr = MagicMock(number=42, merged_at="2026-06-27T00:00:00Z")
        github = MagicMock()
        github.list_prs_for_branch.return_value = [merged_pr]
        service = FlowStatusService(MagicMock(), MagicMock(), github)
        flow_state = {
            "planner_status": "done",
            "executor_status": "done",
            "reviewer_status": "done",
            "pr_ref": "https://github.com/example/repo/pull/42",
        }

        result = service.evaluate_aborted_to_done_eligibility(
            flow_state,
            "task/issue-42",
        )

        assert result == (True, 42)

    def test_cached_merged_pr_avoids_remote_lookup(self) -> None:
        """A caller-provided merged PR is sufficient delivery evidence."""
        from vibe3.services.flow.status import FlowStatusService

        github = MagicMock()
        service = FlowStatusService(MagicMock(), MagicMock(), github)
        cached_pr = MagicMock(number=43, merged_at="2026-06-27T00:00:00Z")
        flow_state = {
            "planner_status": "done",
            "executor_status": "done",
            "reviewer_status": "done",
        }

        result = service.evaluate_aborted_to_done_eligibility(
            flow_state,
            "task/issue-43",
            cached_pr=cached_pr,
        )

        assert result == (True, 43)
        github.list_prs_for_branch.assert_not_called()

    def test_cached_merged_state_confirms_delivery_without_timestamp(self) -> None:
        """GitHub's explicit MERGED state is authoritative without merged_at."""
        from vibe3.models import PRState
        from vibe3.services.flow.status import FlowStatusService

        github = MagicMock()
        github.list_prs_for_branch.return_value = []
        service = FlowStatusService(MagicMock(), MagicMock(), github)
        cached_pr = MagicMock(number=44, merged_at=None, state=PRState.MERGED)
        flow_state = {
            "planner_status": "done",
            "executor_status": "done",
            "reviewer_status": "done",
        }

        result = service.evaluate_aborted_to_done_eligibility(
            flow_state,
            "task/issue-44",
            cached_pr=cached_pr,
        )

        assert result == (True, 44)
        github.list_prs_for_branch.assert_not_called()


class TestFlowList:
    """Tests for listing flows."""

    def test_list_flows_no_filter(self, mock_store, mock_git) -> None:
        """Test listing all flows."""
        mock_store.get_all_flows.return_value = [
            {
                "branch": "branch-1",
                "flow_slug": "flow-1",
                "flow_status": "active",
                "updated_at": "2026-03-16T00:00:00",
            },
            {
                "branch": "branch-2",
                "flow_slug": "flow-2",
                "flow_status": "blocked",
                "updated_at": "2026-03-16T00:00:00",
            },
        ]
        # First call returns links for branch-1
        mock_store.get_issue_links.side_effect = [
            [
                {
                    "branch": "branch-1",
                    "issue_number": 10,
                    "issue_role": "task",
                    "created_at": "2026-03-16T00:00:00",
                }
            ],
            [],  # Second call for branch-2
        ]

        # First call finds worktree for branch-1, second returns None
        mock_git.find_worktree_path_for_branch.side_effect = [
            Path("/wt/branch-1"),
            None,
        ]

        service = FlowService(store=mock_store, git_client=mock_git)
        result = service.list_flows()

        assert len(result) == 2
        assert result[0].branch == "branch-1"
        assert result[0].worktree_root == "/wt/branch-1"
        assert result[0].task_issue_number == 10
        assert result[1].branch == "branch-2"
        assert result[1].worktree_root is None

    def test_list_flows_with_status_filter(self, mock_store, mock_git) -> None:
        """Test listing flows with status filter."""
        mock_store.get_flows_by_status.return_value = [
            {
                "branch": "branch-1",
                "flow_slug": "flow-1",
                "flow_status": "active",
                "updated_at": "2026-03-16T00:00:00",
            },
        ]
        mock_store.get_issue_links.return_value = []
        mock_git.find_worktree_path_for_branch.return_value = Path("/wt/branch-1")

        service = FlowService(store=mock_store, git_client=mock_git)
        result = service.list_flows(status="active")

        assert len(result) == 1
        assert result[0].branch == "branch-1"
        assert result[0].worktree_root == "/wt/branch-1"

    def test_list_flows_skips_unparseable_rows(self, mock_store, mock_git) -> None:
        """Test list_flows skips rows with unknown flow_status without crashing."""
        mock_store.get_all_flows.return_value = [
            {
                "branch": "branch-ok",
                "flow_slug": "flow-ok",
                "flow_status": "active",
                "updated_at": "2026-03-16T00:00:00",
            },
            {
                "branch": "branch-bad",
                "flow_slug": "flow-bad",
                "flow_status": "unknown_future_status",
                "updated_at": "2026-03-16T00:00:00",
            },
        ]
        mock_store.get_issue_links.return_value = []
        mock_git.find_worktree_path_for_branch.return_value = Path("/wt/branch-ok")

        service = FlowService(store=mock_store, git_client=mock_git)
        result = service.list_flows()

        assert len(result) == 1
        assert result[0].branch == "branch-ok"
        assert result[0].worktree_root == "/wt/branch-ok"

    def test_list_flows_computes_scene_completeness(self, mock_store) -> None:
        """Test list_flows computes has_branch/has_worktree/is_placeholder."""
        mock_git = MagicMock(spec=GitClient)
        mock_store.get_all_flows.return_value = [
            {
                "branch": "branch-real",
                "flow_slug": "flow-real",
                "flow_status": "active",
                "updated_at": "2026-03-16T00:00:00",
            },
            {
                "branch": "branch-placeholder",
                "flow_slug": "flow-placeholder",
                "flow_status": "blocked",
                "updated_at": "2026-03-16T00:00:00",
            },
        ]
        mock_store.get_issue_links.return_value = []
        mock_git.find_worktree_path_for_branch.return_value = None
        mock_git.branch_exists.side_effect = lambda branch: branch == "branch-real"

        service = FlowService(store=mock_store, git_client=mock_git)
        result = service.list_flows()

        assert len(result) == 2
        real, placeholder = result
        assert real.branch == "branch-real"
        assert real.has_branch is True
        assert real.is_placeholder is False

        assert placeholder.branch == "branch-placeholder"
        assert placeholder.has_branch is False
        assert placeholder.is_placeholder is True


class TestFlowStatusResolver:
    """Tests for FlowStatusResolver source-aware reads."""

    def test_resolver_local_reads_from_sqlite(self):
        """Without --remote, reads from SQLite only, no fallback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = SQLiteClient(db_path=str(db_path))

            resolver = FlowStatusResolver(store=store)

            # Create flow in SQLite
            store.update_flow_state(
                "dev/issue-123",
                flow_slug="issue-123",
                flow_status="active",
            )

            result = resolver.resolve(
                branch="dev/issue-123",
                remote=False,
            )

            assert result.branch == "dev/issue-123"
            assert result.flow_slug == "issue-123"
            assert result.flow_status == "active"
            assert result.data_source == DataSource.LOCAL_SQLITE

    def test_resolver_auto_fallback_to_issue_body(self):
        """When SQLite missing, falls back to issue body projection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = SQLiteClient(db_path=str(db_path))

            resolver = FlowStatusResolver(store=store)

            # No flow in SQLite (deleted or remote machine)
            with patch("vibe3.clients.GitHubClient") as mock_github_client_class:
                mock_github_client = MagicMock()
                mock_github_client_class.return_value = mock_github_client

                mock_github_client.view_issue.return_value = {
                    "number": 123,
                    "body": """
<!-- vibe3-flow-state-start -->

**Vibe3 Flow State**

- **State**: blocked
- **Blocked by**: #456
- **Blocked reason**: Waiting for dependency

<!-- vibe3-flow-state-end -->
""",
                    "comments": [],
                }

                result = resolver.resolve(
                    branch="dev/issue-123",
                    remote=False,
                    issue_number=123,  # Required for fallback
                )

                assert result.branch == "dev/issue-123"
                assert result.flow_slug == "dev-issue-123"
                assert result.flow_status == "blocked"
                assert result.blocked_by_issue == 456
                assert result.blocked_reason == "Waiting for dependency"
                assert result.data_source == DataSource.ISSUE_BODY_FALLBACK
                mock_github_client.view_issue.assert_called_once_with(
                    123, fields=["body", "comments"]
                )
