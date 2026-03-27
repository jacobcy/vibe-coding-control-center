"""Tests for pre-push inspect summary normalization."""

from vibe3.services.pre_push_inspect_summary import summarize_inspect_payload


def test_sets_async_trigger_when_blocked() -> None:
    summary = summarize_inspect_payload(
        {
            "score": {
                "level": "CRITICAL",
                "score": 12,
                "block": True,
                "block_threshold": 10,
            }
        }
    )

    assert summary.review_trigger == "yes-async"
    assert summary.block_review is True


def test_sets_manual_trigger_for_high_non_blocking_risk() -> None:
    summary = summarize_inspect_payload(
        {
            "score": {
                "level": "HIGH",
                "score": 9,
                "block": False,
                "block_threshold": 10,
            }
        }
    )

    assert summary.review_trigger == "recommended-manual"
    assert summary.block_review is False


def test_defaults_to_no_trigger_without_score_payload() -> None:
    summary = summarize_inspect_payload({})

    assert summary.review_trigger == "no"
    assert summary.risk_level == "LOW"
    assert summary.risk_score == 0
