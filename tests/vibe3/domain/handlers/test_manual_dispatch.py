"""Tests for ManualReviewIntent error paths in manual_dispatch handler.

These cover the CRITICAL fix where sync/dry-run failures must populate
_pending_results["review"] with an ERROR ReviewRunResult. Without this,
vibe3 review base silently treats a crashed/misconfigured review as
fire-and-forget success (exit 0), breaking CI gating.
"""

from __future__ import annotations

from unittest.mock import patch

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
            handle_manual_plan_intent(event)

        result = get_pending_result("plan")
        assert isinstance(result, RuntimeError)
        assert str(result) == "config boom"

    def test_missing_request_stores_error_result(self) -> None:
        event = ManualPlanIntent(
            issue_number=123,
            branch="task/issue-123",
            request=None,
            no_async=True,
        )

        with patch("vibe3.config.load_config_for_role", return_value=object()):
            handle_manual_plan_intent(event)

        result = get_pending_result("plan")
        assert isinstance(result, ValueError)
        assert str(result) == "ManualPlanIntent missing request"


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
            handle_manual_run_intent(event)

        result = get_pending_result("run")
        assert isinstance(result, RuntimeError)
        assert str(result) == "config boom"

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
            handle_manual_run_intent(event)

        result = get_pending_result("run")
        assert isinstance(result, RuntimeError)
        assert str(result) == "run boom"
