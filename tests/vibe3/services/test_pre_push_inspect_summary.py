"""Tests for pre-push inspect summary normalization."""

from vibe3.analysis.pre_push_inspect_summary import summarize_inspect_payload


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


def test_handles_missing_or_null_score_fields() -> None:
    summary = summarize_inspect_payload(
        {
            "score": {
                "level": None,
                "score": None,
                "block": None,
                "block_threshold": None,
                "reason": None,
                "trigger_factors": None,
                "recommendations": None,
            }
        }
    )

    assert summary.review_trigger == "no"
    assert summary.risk_level == "LOW"
    assert summary.risk_score == 0
    assert summary.block_threshold == 12
    assert summary.risk_reason == ""
    assert summary.trigger_factors == []
    assert summary.recommendations == []
