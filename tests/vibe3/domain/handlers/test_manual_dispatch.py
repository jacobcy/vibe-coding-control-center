"""Tests for ManualReviewIntent error paths in manual_dispatch handler.

These cover the CRITICAL fix where sync/dry-run failures must populate
_pending_results["review"] with an ERROR ReviewRunResult. Without this,
vibe3 review base silently treats a crashed/misconfigured review as
fire-and-forget success (exit 0), breaking CI gating.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from vibe3.agents import CodeagentResult
from vibe3.domain.handlers.manual_dispatch import (
    get_pending_result,
    handle_manual_plan_intent,
    handle_manual_review_intent,
    handle_manual_run_intent,
)
from vibe3.models import (
    ManualPlanIntent,
    ManualReviewIntent,
    ManualRunIntent,
    ReviewRequest,
    ReviewScope,
)
from vibe3.roles import ReviewRunResult


def _make_review_request() -> ReviewRequest:
    return ReviewRequest(scope=ReviewScope.for_base("main"))


def _make_review_config(
    backend: str | None = None, model: str | None = None
) -> SimpleNamespace:
    """Create a minimal config mock with review agent_config section."""
    return SimpleNamespace(
        review=SimpleNamespace(
            agent_config=SimpleNamespace(
                agent=None,
                backend=backend,
                model=model,
                timeout_seconds=3600,
            )
        )
    )


class TestManualReviewIntentErrorPaths:
    """Sync/dry-run failure paths must store an ERROR ReviewRunResult."""

    def setup_method(self) -> None:
        # Clear any leftover result from a previous test.
        get_pending_result("review")

    def test_config_load_failure_stores_error_result(self) -> None:
        event = ManualReviewIntent(
            issue_number=123,
            branch="main",
            is_base_review=True,
            request=_make_review_request(),
            no_async=True,
        )

        with patch(
            "vibe3.config.load_config_for_role",
            side_effect=RuntimeError("config boom"),
        ):
            handle_manual_review_intent(event)

        assert get_pending_result("review") == ReviewRunResult("ERROR", None, 123)

    def test_missing_base_review_request_stores_error_result(self) -> None:
        event = ManualReviewIntent(
            issue_number=456,
            branch="main",
            is_base_review=True,
            request=None,
            no_async=True,
        )

        with patch("vibe3.config.load_config_for_role") as mock_load_config:
            mock_load_config.return_value = object()
            handle_manual_review_intent(event)

        assert get_pending_result("review") == ReviewRunResult("ERROR", None, 456)

    def test_execution_exception_stores_error_result(self) -> None:
        event = ManualReviewIntent(
            issue_number=789,
            branch="main",
            is_base_review=True,
            request=_make_review_request(),
            no_async=True,
        )

        with (
            patch("vibe3.config.load_config_for_role") as mock_load_config,
            patch("vibe3.roles.execute_manual_review_sync") as mock_execute,
        ):
            mock_load_config.return_value = object()
            mock_execute.side_effect = RuntimeError("execution boom")
            handle_manual_review_intent(event)

        assert get_pending_result("review") == ReviewRunResult("ERROR", None, 789)

    def test_execution_exception_logs_real_exception(self) -> None:
        """The real caught exception (not a synthetic placeholder) must drive
        log_dispatch_error's classification."""
        event = ManualReviewIntent(
            issue_number=789,
            branch="main",
            is_base_review=True,
            request=_make_review_request(),
            no_async=True,
        )
        real_exc = RuntimeError("execution boom")

        with (
            patch("vibe3.config.load_config_for_role") as mock_load_config,
            patch("vibe3.roles.execute_manual_review_sync") as mock_execute,
            patch(
                "vibe3.domain.handlers.manual_dispatch.log_dispatch_error"
            ) as mock_log_dispatch_error,
        ):
            mock_load_config.return_value = object()
            mock_execute.side_effect = real_exc
            handle_manual_review_intent(event)

        mock_log_dispatch_error.assert_called_once_with(
            "Review dispatch failed", real_exc
        )
        assert get_pending_result("review") == ReviewRunResult("ERROR", None, 789)


class TestManualPlanIntentErrorPaths:
    """Manual plan failures must be visible to the CLI after publish()."""

    def setup_method(self) -> None:
        get_pending_result("plan")

    def test_config_load_failure_stores_error_result(self) -> None:
        event = ManualPlanIntent(
            issue_number=123,
            branch="task/issue-123",
            request=object(),
            no_async=True,
        )

        with patch(
            "vibe3.config.load_config_for_role",
            side_effect=RuntimeError("config boom"),
        ):
            result = handle_manual_plan_intent(event)

        # Handler now returns CodeagentResult with success=False
        assert result is not None
        assert not result.success
        assert "config boom" in result.stderr

    def test_missing_request_stores_error_result(self) -> None:
        event = ManualPlanIntent(
            issue_number=123,
            branch="task/issue-123",
            request=None,
            no_async=True,
        )

        with patch("vibe3.config.load_config_for_role", return_value=object()):
            result = handle_manual_plan_intent(event)

        # Handler now returns CodeagentResult with success=False
        assert result is not None
        assert not result.success
        assert "missing request" in result.stderr


class TestManualRunIntentErrorPaths:
    """Manual run failures must be visible to the CLI after publish()."""

    def setup_method(self) -> None:
        get_pending_result("run")

    def test_config_load_failure_stores_error_result(self) -> None:
        event = ManualRunIntent(
            issue_number=123,
            branch="task/issue-123",
            instructions="do work",
            no_async=True,
        )

        with patch(
            "vibe3.config.load_config_for_role",
            side_effect=RuntimeError("config boom"),
        ):
            result = handle_manual_run_intent(event)

        # Handler now returns CodeagentResult with success=False
        assert result is not None
        assert not result.success
        assert "config boom" in result.stderr

    def test_execution_exception_stores_error_result(self) -> None:
        event = ManualRunIntent(
            issue_number=123,
            branch="task/issue-123",
            instructions="do work",
            no_async=True,
        )

        with (
            patch("vibe3.config.load_config_for_role", return_value=object()),
            patch(
                "vibe3.roles.execute_manual_run",
                side_effect=RuntimeError("run boom"),
            ),
        ):
            result = handle_manual_run_intent(event)

        # Handler now returns CodeagentResult with success=False
        assert result is not None
        assert not result.success
        assert "run boom" in result.stderr


class TestManualPlanIntentSuccessPaths:
    """Success paths must return CodeagentResult with success=True."""

    def test_sync_returns_success_result(self) -> None:
        """Handler returns successful CodeagentResult on sync execution."""
        from pathlib import Path

        from vibe3.models.plan import PlanRequest, PlanScope

        mock_result = CodeagentResult(success=True, handoff_file=Path("plan.md"))
        mock_scope = PlanScope(kind="spec", description="test specification")
        mock_request = PlanRequest(scope=mock_scope, task_guidance="test task")

        event = ManualPlanIntent(
            issue_number=42,
            branch="task/issue-42",
            request=mock_request,
            no_async=True,
        )

        with (
            patch("vibe3.config.load_config_for_role", return_value=object()),
            patch("vibe3.roles.execute_spec_plan_sync", return_value=mock_result),
        ):
            result = handle_manual_plan_intent(event)

        assert result is not None
        assert result.success
        assert result.handoff_file == Path("plan.md")


class TestManualRunIntentSuccessPaths:
    """Success paths must return CodeagentResult with success=True."""

    def test_returns_success_result(self) -> None:
        """Handler returns successful CodeagentResult on execution."""
        from pathlib import Path

        mock_result = CodeagentResult(success=True, handoff_file=Path("run.md"))

        event = ManualRunIntent(
            issue_number=42,
            branch="task/issue-42",
            instructions="do work",
            no_async=True,
        )

        with (
            patch("vibe3.config.load_config_for_role", return_value=object()),
            patch("vibe3.roles.execute_manual_run", return_value=mock_result),
        ):
            result = handle_manual_run_intent(event)

        assert result is not None
        assert result.success
        assert result.handoff_file == Path("run.md")


class TestManualReviewIntentBranchSuccessPaths:
    """Branch review success paths must return ReviewRunResult."""

    def test_branch_sync_returns_success_result(self) -> None:
        """Handler returns ReviewRunResult with verdict OK on branch review."""
        from unittest.mock import MagicMock

        event = ManualReviewIntent(
            issue_number=42,
            branch="task/issue-42",
            is_base_review=False,
            no_async=True,
        )

        mock_config = MagicMock()
        mock_config.review.agent_config.agent = "vibe-reviewer"
        mock_config.review.agent_config.backend = None
        mock_config.review.agent_config.model = None
        mock_config.review.agent_config.timeout_seconds = 3600

        with (
            patch(
                "vibe3.config.load_config_for_role",
                return_value=mock_config,
            ),
            patch("vibe3.execution.run_issue_role_sync"),
        ):
            result = handle_manual_review_intent(event)

        assert result is not None
        assert result.verdict == "OK"


class TestBackendModelPropagation:
    """Tests for backend and model field propagation through handlers."""

    def setup_method(self) -> None:
        """Clear pending results before each test."""
        get_pending_result("plan")
        get_pending_result("run")
        get_pending_result("review")

    def test_handle_manual_plan_propagates_backend_model(self) -> None:
        """handle_manual_plan_intent returns CodeagentResult with backend/model."""
        from pathlib import Path

        from vibe3.models.plan import PlanRequest, PlanScope

        mock_result = CodeagentResult(
            success=True, backend="claude", model="sonnet", handoff_file=Path("plan.md")
        )
        mock_scope = PlanScope(kind="spec", description="test specification")
        mock_request = PlanRequest(scope=mock_scope, task_guidance="test task")

        event = ManualPlanIntent(
            issue_number=42,
            branch="task/issue-42",
            request=mock_request,
            no_async=True,
        )

        with (
            patch("vibe3.config.load_config_for_role", return_value=object()),
            patch("vibe3.roles.execute_spec_plan_sync", return_value=mock_result),
        ):
            result = handle_manual_plan_intent(event)

        assert result is not None
        assert result.success
        assert result.backend == "claude"
        assert result.model == "sonnet"

    def test_handle_manual_run_propagates_backend_model(self) -> None:
        """handle_manual_run_intent returns CodeagentResult with backend/model."""
        from pathlib import Path

        mock_result = CodeagentResult(
            success=True,
            backend="gemini",
            model="gemini-pro",
            handoff_file=Path("run.md"),
        )

        event = ManualRunIntent(
            issue_number=42,
            branch="task/issue-42",
            instructions="do work",
            no_async=True,
        )

        with (
            patch("vibe3.config.load_config_for_role", return_value=object()),
            patch("vibe3.roles.execute_manual_run", return_value=mock_result),
        ):
            result = handle_manual_run_intent(event)

        assert result is not None
        assert result.success
        assert result.backend == "gemini"
        assert result.model == "gemini-pro"

    def test_handle_manual_review_base_propagates_backend_model(self) -> None:
        """handle_manual_review_intent returns ReviewRunResult with backend/model."""
        mock_review_result = ReviewRunResult(
            verdict="PASS",
            handoff_file="audit.md",
            issue_number=42,
            backend="claude",
            model="sonnet",
        )

        event = ManualReviewIntent(
            issue_number=42,
            branch="main",
            is_base_review=True,
            request=_make_review_request(),
            no_async=True,
        )

        with (
            patch("vibe3.config.load_config_for_role", return_value=object()),
            patch(
                "vibe3.roles.execute_manual_review_sync",
                return_value=mock_review_result,
            ),
        ):
            result = handle_manual_review_intent(event)

        assert result is not None
        assert result.verdict == "PASS"
        assert result.backend == "claude"
        assert result.model == "sonnet"

    def test_handle_manual_review_branch_populates_backend_model(self) -> None:
        """Branch review handler populates backend/model from event params."""
        event = ManualReviewIntent(
            issue_number=42,
            branch="task/issue-42",
            is_base_review=False,
            no_async=True,
            backend="claude",
            model="opus",
        )

        with (
            patch("vibe3.config.load_config_for_role", return_value=object()),
            patch("vibe3.execution.run_issue_role_sync"),
        ):
            result = handle_manual_review_intent(event)

        assert result is not None
        assert result.verdict == "OK"
        assert result.backend == "claude"
        assert result.model == "opus"
        assert result.issue_number == 42

    def test_handle_manual_review_branch_sync_fills_from_launch_result(self) -> None:
        """Branch review sync path fills metadata from launch_result."""
        from vibe3.models import ExecutionLaunchResult

        mock_launch = ExecutionLaunchResult(
            launched=True,
            backend="codex",
            model="gpt-5.4",
            tmux_session="vibe3-review-42",
            log_path="temp/logs/review/42.log",
        )

        event = ManualReviewIntent(
            issue_number=42,
            branch="task/issue-42",
            is_base_review=False,
            no_async=True,
            backend="claude",  # event param
            model="opus",  # event param
        )

        with (
            patch("vibe3.config.load_config_for_role", return_value=object()),
            patch(
                "vibe3.execution.run_issue_role_sync",
                return_value=mock_launch,
            ),
        ):
            result = handle_manual_review_intent(event)

        assert result is not None
        assert result.verdict == "OK"
        # Metadata from launch_result when available
        assert result.backend == "claude"  # event param preferred
        assert result.model == "opus"  # event param preferred
        assert result.tmux_session == "vibe3-review-42"
        assert result.log_path == "temp/logs/review/42.log"

    def test_handle_manual_review_branch_async_fills_from_launch_result(self) -> None:
        """Branch review async path fills metadata from launch_result."""
        from vibe3.models import ExecutionLaunchResult

        mock_launch = ExecutionLaunchResult(
            launched=True,
            backend="codex",
            model="gpt-5.4",
            tmux_session="vibe3-review-async-42",
            log_path="temp/logs/review/async/42.log",
        )

        event = ManualReviewIntent(
            issue_number=42,
            branch="task/issue-42",
            is_base_review=False,
            no_async=False,  # async mode
            backend="claude",
            model="opus",
        )

        with (
            patch(
                "vibe3.config.load_config_for_role",
                return_value=_make_review_config(backend="claude", model="opus"),
            ),
            patch(
                "vibe3.execution.run_issue_role_async",
                return_value=mock_launch,
            ),
        ):
            result = handle_manual_review_intent(event)

        assert result is not None
        assert result.verdict == "ASYNC"
        # Metadata from launch_result
        assert result.backend == "claude"  # event param preferred
        assert result.model == "opus"  # event param preferred
        assert result.tmux_session == "vibe3-review-async-42"
        assert result.log_path == "temp/logs/review/async/42.log"

    def test_handle_manual_review_branch_async_failure_returns_error(self) -> None:
        """Branch review async launch failure must surface ERROR verdict.

        Regression guard: the async verdict must not be hardcoded to ASYNC.
        When launch_result.launched is False, downstream consumers (review.py
        exit-code gating) rely on ERROR to signal failure.
        """
        from vibe3.models import ExecutionLaunchResult

        mock_launch = ExecutionLaunchResult(
            launched=False,
            backend="codex",
            model="gpt-5.4",
            reason="tmux session conflict",
            reason_code="launch_failed",
        )

        event = ManualReviewIntent(
            issue_number=42,
            branch="task/issue-42",
            is_base_review=False,
            no_async=False,
        )

        with (
            patch(
                "vibe3.config.load_config_for_role",
                return_value=_make_review_config(backend="claude", model="opus"),
            ),
            patch(
                "vibe3.execution.run_issue_role_async",
                return_value=mock_launch,
            ),
        ):
            result = handle_manual_review_intent(event)

        assert result is not None
        assert result.verdict == "ERROR"
