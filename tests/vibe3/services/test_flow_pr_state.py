"""Tests for flow_pr_state module."""

from datetime import datetime

from vibe3.models.pr import PRResponse, PRState
from vibe3.services.flow_pr_state import evaluate_flow_pr_state


class TestEvaluateFlowPRState:
    """Tests for evaluate_flow_pr_state function."""

    def test_merged_state(self):
        """PRState.MERGED should mark is_merged=True and can_mark_flow_done=True."""
        pr = PRResponse(
            number=42,
            title="Test PR",
            body="",
            state=PRState.MERGED,
            head_branch="task/test",
            base_branch="main",
            url="https://github.com/test/pr/42",
            draft=False,
            is_ready=True,
            ci_passed=True,
            merged_at=datetime(2026, 3, 25),
            created_at=datetime(2026, 3, 20),
            updated_at=datetime(2026, 3, 25),
        )
        result = evaluate_flow_pr_state(pr)

        assert result.pr_found is True
        assert result.pr_number == 42
        assert result.is_merged is True
        assert result.is_closed_not_merged is False
        assert result.can_mark_flow_done is True

    def test_closed_not_merged(self):
        """PRState.CLOSED + merged_at=None should mark is_closed_not_merged=True."""
        pr = PRResponse(
            number=42,
            title="Test PR",
            body="",
            state=PRState.CLOSED,
            head_branch="task/test",
            base_branch="main",
            url="https://github.com/test/pr/42",
            draft=False,
            is_ready=True,
            ci_passed=True,
            merged_at=None,
            created_at=datetime(2026, 3, 20),
            updated_at=datetime(2026, 3, 24),
        )
        result = evaluate_flow_pr_state(pr)

        assert result.pr_found is True
        assert result.pr_number == 42
        assert result.is_merged is False
        assert result.is_closed_not_merged is True
        assert result.can_mark_flow_done is False

    def test_closed_with_merged_at(self):
        """PRState.CLOSED + merged_at set should mark is_merged=True."""
        # GitHub behavior: merged PRs have merged_at set even when closed
        pr = PRResponse(
            number=42,
            title="Test PR",
            body="",
            state=PRState.CLOSED,
            head_branch="task/test",
            base_branch="main",
            url="https://github.com/test/pr/42",
            draft=False,
            is_ready=True,
            ci_passed=True,
            merged_at=datetime(2026, 3, 25),
            created_at=datetime(2026, 3, 20),
            updated_at=datetime(2026, 3, 25),
        )
        result = evaluate_flow_pr_state(pr)

        assert result.pr_found is True
        assert result.pr_number == 42
        assert result.is_merged is True
        assert result.is_closed_not_merged is False
        assert result.can_mark_flow_done is True

    def test_open_pr(self):
        """PRState.OPEN should mark can_mark_flow_done=False."""
        pr = PRResponse(
            number=42,
            title="Test PR",
            body="",
            state=PRState.OPEN,
            head_branch="task/test",
            base_branch="main",
            url="https://github.com/test/pr/42",
            draft=False,
            is_ready=True,
            ci_passed=True,
            merged_at=None,
            created_at=datetime(2026, 3, 20),
            updated_at=datetime(2026, 3, 24),
        )
        result = evaluate_flow_pr_state(pr)

        assert result.pr_found is True
        assert result.pr_number == 42
        assert result.is_merged is False
        assert result.is_closed_not_merged is False
        assert result.can_mark_flow_done is False

    def test_no_pr(self):
        """pr=None should mark pr_found=False."""
        result = evaluate_flow_pr_state(None)

        assert result.pr_found is False
        assert result.pr_number is None
        assert result.is_merged is False
        assert result.is_closed_not_merged is False
        assert result.can_mark_flow_done is False
