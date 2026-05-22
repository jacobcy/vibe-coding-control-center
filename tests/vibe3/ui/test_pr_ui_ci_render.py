"""Tests for CI status rendering in render_pr_details."""

import re
from io import StringIO

from rich.console import Console

from vibe3.models.pr import CICheck, PRResponse, PRState
from vibe3.ui.pr_ui import render_pr_details


def _render_to_plain(pr: PRResponse) -> str:
    """Render PR details and return plain text without ANSI codes."""
    test_console = Console(file=StringIO(), force_terminal=True, no_color=True)
    import vibe3.ui.pr_ui

    original_console = vibe3.ui.pr_ui.console
    vibe3.ui.pr_ui.console = test_console
    try:
        render_pr_details(pr)
    finally:
        vibe3.ui.pr_ui.console = original_console

    # Strip any remaining ANSI escape sequences
    raw = test_console.file.getvalue()
    return re.sub(r"\x1b\[[0-9;]*m", "", raw)


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

        output = _render_to_plain(pr)
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

        output = _render_to_plain(pr)
        assert "1 check(s) failed" in output
        assert "Test" in output
        assert "FAILURE" in output
        assert "View details" in output

    def test_render_ci_failed_includes_failure_category_and_command(self) -> None:
        """Test failed CI rendering includes failure category and command."""
        checks = [
            CICheck(
                name="Test",
                state="FAILURE",
                bucket="fail",
                link="https://github.com/test/repo/actions/runs/2/job/3",
                failure_category="pytest",
                failure_command="gh run view 2 --job 3 --log-failed",
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

        output = _render_to_plain(pr)
        assert "pytest" in output
        assert "gh run view 2 --job 3 --log-failed" in output

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

        output = _render_to_plain(pr)
        assert "1 check(s) pending" in output
        assert "Build" in output

    def test_render_ci_other_bucket(self) -> None:
        """Test rendering when CI checks have unknown bucket."""
        checks = [
            CICheck(
                name="Skipped Check",
                state="SKIPPED",
                bucket="skipping",
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

        output = _render_to_plain(pr)
        assert "CI Status" in output
        assert "1 check(s) in other state" in output
        assert "Skipped Check" in output
        assert "skipping" in output

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

        output = _render_to_plain(pr)
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

        output = _render_to_plain(pr)
        assert "CI Status" in output
        assert "pending" in output

    def test_render_ci_failed_includes_workflow_and_description(self) -> None:
        """Test failed CI rendering includes workflow and description."""
        checks = [
            CICheck(
                name="Test",
                state="FAILURE",
                bucket="fail",
                link="https://github.com/test/repo/actions/runs/2/job/3",
                workflow="CI",
                description="pytest failed",
                failure_category="pytest",
                failure_command="gh run view 2 --job 3 --log-failed",
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

        output = _render_to_plain(pr)
        assert "Workflow: CI" in output
        assert "Description: pytest failed" in output
        assert "pytest" in output
        assert "gh run view 2 --job 3 --log-failed" in output
