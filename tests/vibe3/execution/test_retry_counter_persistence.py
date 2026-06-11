"""Integration tests for retry counter persistence in noop_gate.

Verifies that retry counters are persisted to database correctly:
- Failure path: retry count +1 is written immediately
- Success path: retry count is cleared to 0 immediately
"""

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from vibe3.clients import SQLiteClient
from vibe3.exceptions import GitHubAPIError
from vibe3.execution.noop_gate import apply_unified_noop_gate


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(str(db_path))
        yield store


class TestRetryCounterPersistence:
    """Test retry counter persistence to database."""

    def test_github_api_failure_persists_retry_count(self, temp_db):
        """GitHub API failure should immediately persist retry count to DB."""
        branch = "test-branch"
        issue_number = 123

        # Setup: create flow state
        temp_db.update_flow_state(branch, flow_slug="test")
        flow_state = temp_db.get_flow_state(branch)

        # Execute with mock
        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch("vibe3.services.issue.failure.block_executor_noop_issue"),
        ):
            mock_gh.return_value.view_issue.side_effect = Exception("GitHub API failed")

            # Should raise GitHubAPIError after first failure
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

        # Verify: retry count persisted to database
        flow_state_after = temp_db.get_flow_state(branch)
        assert flow_state_after is not None
        assert flow_state_after.get("noop_gate_github_retry_count") == 1

    def test_malformed_response_persists_retry_count(self, temp_db):
        """Malformed GitHub response should immediately persist retry count to DB."""
        branch = "test-branch"
        issue_number = 123

        # Setup: create flow state
        temp_db.update_flow_state(branch, flow_slug="test")
        flow_state = temp_db.get_flow_state(branch)

        # Execute with mock
        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch("vibe3.services.issue.failure.block_executor_noop_issue"),
        ):
            mock_gh.return_value.view_issue.return_value = None  # Malformed response

            # Should raise GitHubAPIError after first failure
            with pytest.raises(GitHubAPIError, match="Malformed GitHub response"):
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

        # Verify: retry count persisted to database
        flow_state_after = temp_db.get_flow_state(branch)
        assert flow_state_after is not None
        assert flow_state_after.get("noop_gate_malformed_retry_count") == 1

    def test_success_clears_retry_counts_in_database(self, temp_db):
        """Successful state change should clear retry counts in DB."""
        branch = "test-branch"
        issue_number = 123

        # Setup: create flow state with existing retry counts
        temp_db.update_flow_state(
            branch,
            flow_slug="test",
            noop_gate_github_retry_count=2,
            noop_gate_malformed_retry_count=1,
        )
        flow_state = temp_db.get_flow_state(branch)

        # Execute with mock
        with patch("vibe3.clients.github_client.GitHubClient") as mock_gh:
            mock_gh.return_value.view_issue.return_value = {
                "labels": [{"name": "state/done"}]  # State changed
            }

            # Should succeed and clear retry counts
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

        # Verify: retry counts cleared in database
        flow_state_after = temp_db.get_flow_state(branch)
        assert flow_state_after is not None
        assert flow_state_after.get("noop_gate_github_retry_count") == 0
        assert flow_state_after.get("noop_gate_malformed_retry_count") == 0

    def test_retry_limit_records_error_after_3_failures(self, temp_db):
        """After 3 GitHub API failures, should record error, not block flow."""
        branch = "test-branch"
        issue_number = 123

        # Setup: create flow state with retry count at limit
        temp_db.update_flow_state(
            branch,
            flow_slug="test",
            noop_gate_github_retry_count=3,
        )
        flow_state = temp_db.get_flow_state(branch)

        # Execute with mock
        with patch("vibe3.clients.github_client.GitHubClient") as mock_gh:
            mock_gh.return_value.view_issue.side_effect = Exception("GitHub API failed")

            with pytest.raises(
                GitHubAPIError, match="Cannot verify remote state.*after 3 retries"
            ):
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

        # Verify: flow NOT blocked (no blocked_reason)
        flow_state_after = temp_db.get_flow_state(branch)
        assert flow_state_after is not None
        assert flow_state_after.get("blocked_reason") is None

        # Verify: error recorded to error_log (FailedGate will control dispatch)
        # Note: error_log verification requires ErrorTrackingService query
        # which is tested in test_error_tracking.py

    def test_retry_limit_records_current_tick_id(self, temp_db):
        """Retry-limit error should preserve the heartbeat tick id in error_log."""
        branch = "test-branch"
        issue_number = 123

        temp_db.update_flow_state(
            branch, flow_slug="test", noop_gate_github_retry_count=3
        )
        flow_state = temp_db.get_flow_state(branch)

        with patch("vibe3.clients.github_client.GitHubClient") as mock_gh:
            mock_gh.return_value.view_issue.side_effect = Exception("GitHub API failed")

            with pytest.raises(
                GitHubAPIError, match="Cannot verify remote state.*after 3 retries"
            ):
                apply_unified_noop_gate(
                    store=temp_db,
                    issue_number=issue_number,
                    branch=branch,
                    actor="test",
                    role="executor",
                    before_state_label="state/running",
                    repo="owner/repo",
                    flow_state=flow_state,
                    tick_id=9,
                )

        with sqlite3.connect(temp_db.db_path) as conn:
            rows = conn.execute("""
                SELECT tick_id, error_code
                FROM error_log
                ORDER BY id DESC
                LIMIT 1
                """).fetchall()
        assert rows == [(9, "E_API_UNAVAILABLE")]
