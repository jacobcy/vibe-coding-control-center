"""Tests for CI status rendering in render_pr_details."""

from io import StringIO
from unittest.mock import patch

from vibe3.models.pr import CICheck, PRResponse, PRState
from vibe3.ui.pr_ui import render_pr_details


class TestPRUICIRender:
    """Test suite for CI status rendering."""

    def test_render_ci_passed(self) -> None:
        """Test rendering when all CI checks pass."""
        checks = [
            CICheck(
                name="Build",
                state="SUCCESS",
                bucket="pass",
                link="https://github.com/test/repo/actions/runs/1",
            ),
            CICheck(
                name="Test",
                state="SUCCESS",
                bucket="pass",
                link="https://github.com/test/repo/actions/runs/2",
            ),
        ]

        pr = PRResponse(
            number=123,
            title="Test PR",
            state=PRState.OPEN,
            head_branch="feature",
            base_branch="main",
            url="https://github.com/test/repo/pull/123",
            ci_checks=checks,
        )

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            render_pr_details(pr)
            output = mock_stdout.getvalue()

        assert "✓ All checks passed" in output
        assert "CI Status" in output

    def test_render_ci_failed(self) -> None:
        """Test rendering when CI checks fail."""
        checks = [
            CICheck(
                name="Build",
                state="SUCCESS",
                bucket="pass",
                link="https://github.com/test/repo/actions/runs/1",
            ),
            CICheck(
                name="Test",
                state="FAILURE",
                bucket="fail",
                link="https://github.com/test/repo/actions/runs/2",
            ),
        ]

        pr = PRResponse(
            number=123,
            title="Test PR",
            state=PRState.OPEN,
            head_branch="feature",
            base_branch="main",
            url="https://github.com/test/repo/pull/123",
            ci_checks=checks,
        )

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            render_pr_details(pr)
            output = mock_stdout.getvalue()

        assert "✗ 1 check(s) failed" in output
        assert "Test" in output
        assert "FAILURE" in output
        assert "View details" in output

    def test_render_ci_pending(self) -> None:
        """Test rendering when CI checks are pending."""
        checks = [
            CICheck(
                name="Build",
                state="PENDING",
                bucket="pending",
                link="https://github.com/test/repo/actions/runs/1",
            ),
        ]

        pr = PRResponse(
            number=123,
            title="Test PR",
            state=PRState.OPEN,
            head_branch="feature",
            base_branch="main",
            url="https://github.com/test/repo/pull/123",
            ci_checks=checks,
        )

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            render_pr_details(pr)
            output = mock_stdout.getvalue()

        assert "● 1 check(s) pending" in output
        assert "Build" in output

    def test_render_ci_fallback_to_ci_passed(self) -> None:
        """Test fallback to ci_passed when ci_checks is empty."""
        pr = PRResponse(
            number=123,
            title="Test PR",
            state=PRState.OPEN,
            head_branch="feature",
            base_branch="main",
            url="https://github.com/test/repo/pull/123",
            ci_checks=[],
            ci_passed=True,
        )

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            render_pr_details(pr)
            output = mock_stdout.getvalue()

        assert "✓ Passed" in output

    def test_render_ci_fallback_to_ci_status(self) -> None:
        """Test fallback to ci_status when ci_checks is empty and ci_passed is False."""
        pr = PRResponse(
            number=123,
            title="Test PR",
            state=PRState.OPEN,
            head_branch="feature",
            base_branch="main",
            url="https://github.com/test/repo/pull/123",
            ci_checks=[],
            ci_passed=False,
            ci_status="pending",
        )

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            render_pr_details(pr)
            output = mock_stdout.getvalue()

        assert "CI Status" in output
        assert "pending" in output
