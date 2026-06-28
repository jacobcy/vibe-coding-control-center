"""Tests for evidence-only PR reviewer briefing."""

from unittest.mock import ANY, MagicMock, patch

from vibe3.models import (
    KernelImpact,
    KernelObservation,
    ReviewDepth,
    ReviewObservation,
    ReviewPolicy,
)
from vibe3.services.pr.review import SENTINEL, PRReviewBriefingService


def _pr() -> MagicMock:
    pr = MagicMock()
    pr.base_branch = "main"
    pr.head_branch = "feat/test"
    pr.metadata.task_issue = 42
    return pr


def _observation() -> ReviewObservation:
    return ReviewObservation(
        status="ready",
        kernel=KernelObservation(impact=KernelImpact.LARGE),
        review=ReviewPolicy(minimum_depth=ReviewDepth.REPEATED),
    )


def test_render_briefing_contains_review_evidence_without_risk_claims() -> None:
    service = PRReviewBriefingService(MagicMock())

    body = service._render_briefing(123, _pr(), _observation())

    assert SENTINEL in body
    assert "Route:** `main` ← `feat/test`" in body
    assert "Kernel impact:** `large`" in body
    assert "Minimum review depth:** `repeated`" in body
    assert "Risk" not in body
    assert "Impacted Modules" not in body


def test_publish_briefing_creates_new_if_no_sentinel_exists() -> None:
    client = MagicMock()
    client.get_pr.return_value = _pr()
    client.list_pr_comments.return_value = [{"id": "111", "body": "Normal"}]
    client.create_pr_comment.return_value = "https://github.com/comment/new"

    service = PRReviewBriefingService(client)
    with patch.object(service, "_load_observation", return_value=_observation()):
        url = service.publish_briefing(123)

    assert url == "https://github.com/comment/new"
    client.create_pr_comment.assert_called_once_with(123, ANY)


def test_publish_briefing_updates_existing_sentinel() -> None:
    client = MagicMock()
    client.get_pr.return_value = _pr()
    client.list_pr_comments.return_value = [
        {"id": "999", "body": f"Old briefing {SENTINEL}"}
    ]
    client.update_pr_comment.return_value = "https://github.com/comment/999"

    service = PRReviewBriefingService(client)
    with patch.object(service, "_load_observation", return_value=None):
        url = service.publish_briefing(123)

    assert url == "https://github.com/comment/999"
    client.update_pr_comment.assert_called_once_with("999", ANY)
