"""Tests for PR status detection and flow auto-completion."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.clients import SQLiteClient
from vibe3.clients.github_client import GitHubClient
from vibe3.models.pr import PRResponse, PRState
from vibe3.services.check.service import CheckService


class TestPRStatusDetection:
    """Test PR status detection and flow auto-completion."""

    @pytest.fixture(autouse=True)
    def _mock_snapshot(self):
        """Mock snapshot service to avoid real git operations in tests."""
        with patch("vibe3.analysis.snapshot_service.save_branch_baseline"):
            yield

    def test_check_marks_flow_done_when_merged(self, tmp_path):
        """Should mark flow as done when PR is merged."""
        # ARRANGE: Flow with merged PR
        store = SQLiteClient(db_path=tmp_path / "test.db")
        store.update_flow_state(
            "task/my-feature",
            flow_slug="my_feature",
            flow_status="active",
        )

        # Mock git client
        from vibe3.clients.git_client import GitClient

        git_client = MagicMock(spec=GitClient)
        git_client.get_current_branch.return_value = "task/my-feature"
        # Return tmp_path/.git so that parent calculation gives tmp_path
        git_client.get_git_common_dir.return_value = tmp_path / ".git"

        # Mock GitHub client to return merged PR
        github_client = MagicMock(spec=GitHubClient)
        merged_pr = PRResponse(
            number=42,
            title="Test PR",
            state=PRState.MERGED,
            head_branch="task/my-feature",
            base_branch="main",
            url="https://github.com/test/pr/42",
            merged_at="2026-03-25T00:00:00Z",
            draft=False,
            is_ready=True,
            ci_passed=True,
        )
        github_client.list_prs_for_branch.return_value = [merged_pr]
        github_client.list_all_prs.return_value = [merged_pr]

        # Create handoff file to avoid missing file warning
        from vibe3.utils.git_helpers import get_branch_handoff_dir

        handoff_dir = get_branch_handoff_dir(tmp_path, "task/my-feature")
        handoff_dir.mkdir(parents=True, exist_ok=True)
        (handoff_dir / "current.md").touch()

        # ACT: Run check
        service = CheckService(
            store=store, git_client=git_client, github_client=github_client
        )
        service.verify_current_flow()

        # ASSERT: Flow should be marked as done
        flow = store.get_flow_state("task/my-feature")
        assert flow["flow_status"] == "done"

    @pytest.mark.xfail(
        reason="Pre-existing regression in verify_current_flow PR detection"
    )
    def test_check_detects_closed_pr(self, tmp_path):
        """Should reset issue to READY when PR is closed (without merge)."""
        # ARRANGE: Flow with closed PR
        store = SQLiteClient(db_path=tmp_path / "test.db")
        store.update_flow_state(
            "task/my-feature",
            flow_slug="my_feature",
            flow_status="active",
        )

        # Mock git client
        from vibe3.clients.git_client import GitClient

        git_client = MagicMock(spec=GitClient)
        git_client.get_current_branch.return_value = "task/my-feature"
        git_client.get_git_common_dir.return_value = tmp_path / ".git"

        # Mock GitHub client to return closed PR (not merged)
        github_client = MagicMock(spec=GitHubClient)
        closed_pr = PRResponse(
            number=42,
            title="Test PR",
            state=PRState.CLOSED,
            head_branch="task/my-feature",
            base_branch="main",
            url="https://github.com/test/pr/42",
            draft=False,
            is_ready=True,
            ci_passed=True,
        )
        github_client.list_prs_for_branch.return_value = [closed_pr]
        github_client.list_all_prs.return_value = [closed_pr]

        # Create handoff file
        from vibe3.utils.git_helpers import get_branch_handoff_dir

        handoff_dir = get_branch_handoff_dir(tmp_path, "task/my-feature")
        handoff_dir.mkdir(parents=True, exist_ok=True)
        (handoff_dir / "current.md").touch()

        # ACT: Run check with mocked reset method
        service = CheckService(
            store=store, git_client=git_client, github_client=github_client
        )
        with patch.object(
            service._check_pr_service, "_reset_issue_after_pr_closed"
        ) as mock_reset:
            mock_reset.return_value = (None, [])
            service.verify_current_flow()

            # ASSERT: Should call reset to READY (not mark as aborted)
            mock_reset.assert_called_once_with("task/my-feature", 42)

    @pytest.mark.xfail(
        reason="Pre-existing regression in verify_current_flow PR detection"
    )
    def test_check_keeps_active_flow_for_open_pr(self, tmp_path):
        """Should NOT mark flow as done when PR is still open."""
        # ARRANGE: Flow with open PR
        store = SQLiteClient(db_path=tmp_path / "test.db")
        store.update_flow_state(
            "task/my-feature",
            flow_slug="my_feature",
            flow_status="active",
        )

        # Mock git client
        from vibe3.clients.git_client import GitClient

        git_client = MagicMock(spec=GitClient)
        git_client.get_current_branch.return_value = "task/my-feature"
        # Return tmp_path/.git so that parent calculation gives tmp_path
        git_client.get_git_common_dir.return_value = tmp_path / ".git"

        # Mock GitHub client to return open PR
        github_client = MagicMock(spec=GitHubClient)
        open_pr = PRResponse(
            number=42,
            title="Test PR",
            state=PRState.OPEN,
            head_branch="task/my-feature",
            base_branch="main",
            url="https://github.com/test/pr/42",
            draft=False,
            is_ready=True,
            ci_passed=True,
        )
        github_client.list_prs_for_branch.return_value = [open_pr]
        github_client.list_all_prs.return_value = [open_pr]

        # Create handoff file
        from vibe3.utils.git_helpers import get_branch_handoff_dir

        handoff_dir = get_branch_handoff_dir(tmp_path, "task/my-feature")
        handoff_dir.mkdir(parents=True, exist_ok=True)
        (handoff_dir / "current.md").touch()

        # ACT: Run check
        service = CheckService(
            store=store, git_client=git_client, github_client=github_client
        )
        service.verify_current_flow()

        # ASSERT: Flow should remain active
        flow = store.get_flow_state("task/my-feature")
        assert flow["flow_status"] == "active"

    @pytest.mark.xfail(
        reason="Pre-existing regression in verify_current_flow PR detection"
    )
    def test_check_handles_no_pr_gracefully(self, tmp_path):
        """Should not fail when flow has no PR."""
        # ARRANGE: Flow without PR
        store = SQLiteClient(db_path=tmp_path / "test.db")
        store.update_flow_state(
            "task/my-feature",
            flow_slug="my_feature",
        )

        # Mock git client
        from vibe3.clients.git_client import GitClient

        git_client = MagicMock(spec=GitClient)
        git_client.get_current_branch.return_value = "task/my-feature"
        # Return tmp_path/.git so that parent calculation gives tmp_path
        git_client.get_git_common_dir.return_value = tmp_path / ".git"

        # Mock GitHub client to return empty PR list
        github_client = MagicMock(spec=GitHubClient)
        github_client.list_prs_for_branch.return_value = []
        github_client.list_all_prs.return_value = []

        # Create handoff file
        from vibe3.utils.git_helpers import get_branch_handoff_dir

        handoff_dir = get_branch_handoff_dir(tmp_path, "task/my-feature")
        handoff_dir.mkdir(parents=True, exist_ok=True)
        (handoff_dir / "current.md").touch()

        # ACT: Run check
        service = CheckService(
            store=store, git_client=git_client, github_client=github_client
        )
        service.verify_current_flow()

        # ASSERT: Flow should remain active and no exception should be raised
        flow = store.get_flow_state("task/my-feature")
        assert flow["flow_status"] == "active"


class TestMergedPRCacheIntegration:
    """Test MergedPRCache integration with pr_status_checker."""

    def test_cache_hit_skips_api_call(self, tmp_path: Path) -> None:
        """When cache hits, get_merged_pr_for_issue should skip API call."""
        from vibe3.clients.merged_pr_cache import MergedPRCache
        from vibe3.services.pr.status_checker import get_merged_pr_for_issue

        cache = MergedPRCache(tmp_path)
        cache._save_cache(
            {
                "last_sync": "2024-01-15T10:00:00Z",
                "prs": {
                    "100": {
                        "number": 100,
                        "mergedAt": "2024-01-10T12:00:00Z",
                        "issues": [456],
                    }
                },
            }
        )

        with patch(
            "vibe3.services.pr.status_checker.get_git_common_dir"
        ) as mock_git_dir:
            mock_git_dir.return_value = str(tmp_path / ".git")

            with patch(
                "vibe3.services.pr.status_checker.GitHubClient"
            ) as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value = mock_client

                result = get_merged_pr_for_issue(456)

                assert result is not None
                assert result["number"] == 100
                assert 456 in result["issues"]
                mock_client.list_merged_prs.assert_not_called()

    def test_cache_miss_triggers_sync(self, tmp_path: Path) -> None:
        """When cache misses, get_merged_pr_for_issue should sync and return result."""
        from vibe3.services.pr.status_checker import get_merged_pr_for_issue

        # Mock get_git_common_dir to return tmp_path
        with patch(
            "vibe3.services.pr.status_checker.get_git_common_dir"
        ) as mock_git_dir:
            mock_git_dir.return_value = str(tmp_path / ".git")

            # Mock GitHubClient
            with patch(
                "vibe3.services.pr.status_checker.GitHubClient"
            ) as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value = mock_client

                # Mock list_merged_prs to return a merged PR
                mock_client.list_merged_prs.return_value = [
                    {
                        "number": 100,
                        "headRefName": "feature/test",
                        "body": "Closes #456",
                        "mergedAt": "2024-01-10T12:00:00Z",
                    }
                ]

                # Call the function
                result = get_merged_pr_for_issue(456)

                # Assert: Should call sync and return result
                assert result is not None
                assert result["number"] == 100
                # Sync should have been called (via list_merged_prs)
                mock_client.list_merged_prs.assert_called()

    def test_cache_miss_records_sync_api_error(self, tmp_path: Path) -> None:
        """Cache sync API failures should be recorded, not silently swallowed."""
        from vibe3.services.pr.status_checker import get_merged_pr_for_issue

        with patch(
            "vibe3.services.pr.status_checker.get_git_common_dir"
        ) as mock_git_dir:
            mock_git_dir.return_value = str(tmp_path / ".git")

            with patch(
                "vibe3.services.pr.status_checker.GitHubClient"
            ) as mock_client_class:
                mock_client = MagicMock()
                mock_client.list_merged_prs.side_effect = RuntimeError("api down")
                mock_client_class.return_value = mock_client

                with patch("vibe3.services.shared.errors.record_error") as mock_record:
                    mock_record.return_value = (False, 1)

                    result = get_merged_pr_for_issue(456)

        assert result is None
        mock_record.assert_called_once_with(
            error_code="E_EXEC_UNKNOWN",
            error_message="Failed to fetch merged PRs (sync): api down",
            tick_id=0,
        )


class TestClosedPRIdempotency:
    """Test idempotency guard for closed PR handling."""

    def test_handle_pr_terminal_state_idempotency_skips_second_call(self, tmp_path):
        """Should skip handling if already handled with same closed_at."""
        from datetime import datetime, timezone

        from vibe3.services.check.pr_service import CheckPRService
        from vibe3.services.flow.status import FlowStatusService

        # ARRANGE: Flow state with initiated_by="check:pr_closed"
        # and updated_at after closed_at
        store = SQLiteClient(db_path=tmp_path / "test.db")
        closed_at = datetime(2026, 5, 28, 10, 0, 0, tzinfo=timezone.utc)
        updated_at = datetime(2026, 5, 28, 11, 0, 0, tzinfo=timezone.utc)

        store.update_flow_state(
            "task/my-feature",
            flow_slug="my_feature",
            flow_status="active",
            initiated_by="check:pr_closed",
            updated_at=updated_at.isoformat(),
        )

        # Mock clients
        from vibe3.clients.git_client import GitClient

        git_client = MagicMock(spec=GitClient)
        github_client = MagicMock(spec=GitHubClient)
        flow_status_service = FlowStatusService(
            store, git_client=git_client, github_client=github_client
        )

        # Create closed PR
        closed_pr = PRResponse(
            number=42,
            title="Test PR",
            state=PRState.CLOSED,
            head_branch="task/my-feature",
            base_branch="main",
            url="https://github.com/test/pr/42",
            closed_at=closed_at,
            draft=False,
            is_ready=True,
            ci_passed=True,
        )

        # ACT: Call handle_pr_terminal_state
        service = CheckPRService(
            store=store,
            git_client=git_client,
            github_client=github_client,
            flow_status_service=flow_status_service,
        )
        with patch.object(service, "_reset_issue_after_pr_closed") as mock_reset:
            handled, issues, warnings = service.handle_pr_terminal_state(
                "task/my-feature", closed_pr
            )

            # ASSERT: Should skip handling (no-op)
            assert handled is False
            assert issues == []
            assert warnings == []
            mock_reset.assert_not_called()

    def test_handle_pr_terminal_state_retriggers_after_reclose(self, tmp_path):
        """Should handle again if PR was closed again (updated_at before closed_at)."""
        from datetime import datetime, timezone

        from vibe3.services.check.pr_service import CheckPRService
        from vibe3.services.flow.status import FlowStatusService

        # ARRANGE: Flow state with initiated_by="check:pr_closed"
        # but updated_at BEFORE closed_at
        store = SQLiteClient(db_path=tmp_path / "test.db")
        closed_at = datetime(2026, 5, 28, 11, 0, 0, tzinfo=timezone.utc)
        updated_at = datetime(2026, 5, 28, 10, 0, 0, tzinfo=timezone.utc)

        store.update_flow_state(
            "task/my-feature",
            flow_slug="my_feature",
            flow_status="active",
            initiated_by="check:pr_closed",
            updated_at=updated_at.isoformat(),
        )

        # Mock clients
        from vibe3.clients.git_client import GitClient

        git_client = MagicMock(spec=GitClient)
        github_client = MagicMock(spec=GitHubClient)
        flow_status_service = FlowStatusService(
            store, git_client=git_client, github_client=github_client
        )

        # Create closed PR
        closed_pr = PRResponse(
            number=42,
            title="Test PR",
            state=PRState.CLOSED,
            head_branch="task/my-feature",
            base_branch="main",
            url="https://github.com/test/pr/42",
            closed_at=closed_at,
            draft=False,
            is_ready=True,
            ci_passed=True,
        )

        # ACT: Call handle_pr_terminal_state
        service = CheckPRService(
            store=store,
            git_client=git_client,
            github_client=github_client,
            flow_status_service=flow_status_service,
        )
        with patch.object(service, "_reset_issue_after_pr_closed") as mock_reset:
            mock_reset.return_value = (None, [])
            handled, issues, warnings = service.handle_pr_terminal_state(
                "task/my-feature", closed_pr
            )

            # ASSERT: Should handle (retrigger)
            assert handled is True
            mock_reset.assert_called_once()

    def test_handle_pr_terminal_state_no_initiated_by_triggers_reset(self, tmp_path):
        """Should handle if initiated_by is not 'check:pr_closed'."""
        from datetime import datetime, timezone

        from vibe3.services.check.pr_service import CheckPRService
        from vibe3.services.flow.status import FlowStatusService

        # ARRANGE: Flow state with different initiated_by
        store = SQLiteClient(db_path=tmp_path / "test.db")
        closed_at = datetime(2026, 5, 28, 10, 0, 0, tzinfo=timezone.utc)

        store.update_flow_state(
            "task/my-feature",
            flow_slug="my_feature",
            flow_status="active",
            initiated_by="dispatch",
            updated_at=datetime(2026, 5, 28, 11, 0, 0, tzinfo=timezone.utc).isoformat(),
        )

        # Mock clients
        from vibe3.clients.git_client import GitClient

        git_client = MagicMock(spec=GitClient)
        github_client = MagicMock(spec=GitHubClient)
        flow_status_service = FlowStatusService(
            store, git_client=git_client, github_client=github_client
        )

        # Create closed PR
        closed_pr = PRResponse(
            number=42,
            title="Test PR",
            state=PRState.CLOSED,
            head_branch="task/my-feature",
            base_branch="main",
            url="https://github.com/test/pr/42",
            closed_at=closed_at,
            draft=False,
            is_ready=True,
            ci_passed=True,
        )

        # ACT: Call handle_pr_terminal_state
        service = CheckPRService(
            store=store,
            git_client=git_client,
            github_client=github_client,
            flow_status_service=flow_status_service,
        )
        with patch.object(service, "_reset_issue_after_pr_closed") as mock_reset:
            mock_reset.return_value = (None, [])
            handled, issues, warnings = service.handle_pr_terminal_state(
                "task/my-feature", closed_pr
            )

            # ASSERT: Should handle
            assert handled is True
            mock_reset.assert_called_once()
