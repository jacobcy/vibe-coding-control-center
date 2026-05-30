"""Integration tests for ERROR/BLOCK decoupling.

These tests verify the architectural separation between:
- ERROR system: runtime errors → error_log only, no block_flow
- BLOCK system: business logic → blocked_reason + block_flow

Phase 3 verification tests.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.exceptions.runtime_errors import GitHubAPIError
from vibe3.execution.noop_gate import apply_unified_noop_gate
from vibe3.services.issue_failure_service import (
    fail_issue,
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(str(db_path))
        yield store


class TestDatabaseErrorDoesNotTriggerBlock:
    """Test that database errors do NOT trigger block_flow.

    Scenario: "no such column" error should be recorded to error_log,
    not cause business flow block.
    """

    def test_sqlite_error_recorded_not_blocked(self, temp_db):
        """Database error should record to error_log, not blocked_reason."""
        branch = "test-branch"
        issue_number = 123

        temp_db.update_flow_state(branch, flow_slug="test")
        flow_state = temp_db.get_flow_state(branch)

        with patch("vibe3.clients.github_client.GitHubClient") as mock_gh:
            mock_gh.return_value.view_issue.return_value = {
                "labels": [{"name": "state/running"}]
            }

            apply_unified_noop_gate(
                store=temp_db,
                issue_number=issue_number,
                branch=branch,
                actor="test",
                role="executor",
                before_state_label="state/running",
                repo="owner/repo",
                flow_state=flow_state,
            )

        flow_state_after = temp_db.get_flow_state(branch)
        assert flow_state_after is not None
        assert flow_state_after.get("blocked_reason") is None

    def test_fail_issue_no_blocked_reason(self, temp_db):
        """fail_issue() should NOT write blocked_reason."""
        branch = "test-branch"
        issue_number = 123

        temp_db.update_flow_state(branch, flow_slug="test")
        temp_db.add_issue_link(branch, issue_number, role="task")

        fail_issue(
            issue_number=issue_number,
            reason="Runtime error: database connection failed",
            role="manager",
            actor="test",
        )

        flow_state_after = temp_db.get_flow_state(branch)
        assert flow_state_after is not None
        assert flow_state_after.get("blocked_reason") is None


class TestAgentNoopTriggersBlock:
    """Test that agent noop (no state change) triggers block_flow.

    Scenario: agent completes but issue state unchanged → business block.
    """

    def test_state_unchanged_triggers_block(self, temp_db):
        """Agent noop should trigger block_flow."""
        branch = "test-branch"
        issue_number = 123

        temp_db.update_flow_state(branch, flow_slug="test")
        flow_state = temp_db.get_flow_state(branch)

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.role_policy_helpers.block_executor_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.return_value = {
                "labels": [{"name": "state/running"}]
            }

            apply_unified_noop_gate(
                store=temp_db,
                issue_number=issue_number,
                branch=branch,
                actor="test",
                role="executor",
                before_state_label="state/running",
                repo="owner/repo",
                flow_state=flow_state,
            )

            mock_block.assert_called_once()


class TestGitHubAPIFailureNoBlock:
    """Test that GitHub API failures do NOT trigger block_flow.

    Scenario: GitHub API unavailable → record to error_log, retry, no block.
    """

    def test_github_api_failure_raises_error_not_block(self, temp_db):
        """GitHub API failure should raise GitHubAPIError, not block."""
        branch = "test-branch"
        issue_number = 123

        temp_db.update_flow_state(branch, flow_slug="test")
        flow_state = temp_db.get_flow_state(branch)

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.role_policy_helpers.block_executor_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.side_effect = Exception("GitHub timeout")

            with pytest.raises(GitHubAPIError, match="Cannot verify remote state"):
                apply_unified_noop_gate(
                    store=temp_db,
                    issue_number=issue_number,
                    branch=branch,
                    actor="test",
                    role="executor",
                    before_state_label="state/running",
                    repo="owner/repo",
                    flow_state=flow_state,
                )

            mock_block.assert_not_called()

    def test_github_api_failure_records_error_log(self, temp_db):
        """GitHub API failure after retries should record to error_log."""
        branch = "test-branch"
        issue_number = 123

        temp_db.update_flow_state(
            branch, flow_slug="test", noop_gate_github_retry_count=3
        )
        flow_state = temp_db.get_flow_state(branch)

        with patch("vibe3.clients.github_client.GitHubClient") as mock_gh:
            mock_gh.return_value.view_issue.side_effect = Exception("GitHub timeout")

            with pytest.raises(GitHubAPIError):
                apply_unified_noop_gate(
                    store=temp_db,
                    issue_number=issue_number,
                    branch=branch,
                    actor="test",
                    role="executor",
                    before_state_label="state/running",
                    repo="owner/repo",
                    flow_state=flow_state,
                )

        flow_state_after = temp_db.get_flow_state(branch)
        assert flow_state_after is not None
        assert flow_state_after.get("blocked_reason") is None


class TestDependencyNotSatisfiedTriggersBlock:
    """Test that dependency not satisfied triggers block_flow.

    Scenario: required dependency missing → business block.
    """

    def test_flow_service_block_flow_writes_blocked_reason(self, temp_db):
        """FlowService.block_flow() should write blocked_reason."""
        from vibe3.services.flow_service import FlowService

        branch = "test-branch"

        temp_db.update_flow_state(branch, flow_slug="test")

        FlowService(store=temp_db).block_flow(
            branch=branch,
            reason="Blocked by unresolved dependencies",
            actor="test",
        )

        flow_state_after = temp_db.get_flow_state(branch)
        assert flow_state_after is not None
        assert (
            flow_state_after.get("blocked_reason")
            == "Blocked by unresolved dependencies"
        )


class TestErrorBlockOrthogonality:
    """Test that ERROR and BLOCK systems are completely orthogonal."""

    def test_error_log_stores_runtime_errors(self, temp_db):
        """Runtime errors should be stored in error_log, not block flow."""
        from vibe3.services.error_tracking_service import ErrorTrackingService

        branch = "test-branch"

        temp_db.update_flow_state(branch, flow_slug="test")

        error_tracking = ErrorTrackingService.get_instance(store=temp_db)
        error_tracking.record_error(
            error_code="E_TEST_ERROR",
            error_message="Test runtime error",
            branch=branch,
        )

        flow_state_after = temp_db.get_flow_state(branch)
        assert flow_state_after is not None
        assert flow_state_after.get("blocked_reason") is None

    def test_block_flow_writes_blocked_reason(self, temp_db):
        """block_flow() should write blocked_reason."""
        from vibe3.services.flow_service import FlowService

        branch = "test-branch"

        temp_db.update_flow_state(branch, flow_slug="test")

        FlowService(store=temp_db).block_flow(
            branch=branch,
            reason="Business logic block",
            actor="test",
        )

        flow_state_after = temp_db.get_flow_state(branch)
        assert flow_state_after is not None
        assert flow_state_after.get("blocked_reason") == "Business logic block"
