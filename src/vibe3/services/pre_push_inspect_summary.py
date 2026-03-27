"""Normalize inspect-base score output for pre-push hook orchestration."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from typing import Any, Literal

from vibe3.services.inspect_output_adapter import score as inspect_score

ReviewTrigger = Literal["yes-async", "recommended-manual", "no"]


@dataclass(frozen=True)
class PrePushInspectSummary:
    """Structured inspect summary consumed by pre-push orchestration."""

    risk_level: str
    risk_score: int
    block_review: bool
    block_threshold: int
    risk_reason: str
    trigger_factors: list[str]
    recommendations: list[str]
    review_trigger: ReviewTrigger


def _coerce_int(value: object, default: int) -> int:
    """Convert value to int with safe fallback."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return default
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def _coerce_list(value: object) -> list[str]:
    """Convert value to list[str] with safe fallback."""
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def summarize_inspect_payload(payload: dict[str, object]) -> PrePushInspectSummary:
    """Convert raw inspect output into stable pre-push summary."""
    score_data = inspect_score(payload)
    risk_level = str(score_data.get("level") or "LOW")
    block_review = bool(score_data.get("block", False))

    review_trigger: ReviewTrigger = "no"
    if block_review:
        review_trigger = "yes-async"
    elif risk_level in {"HIGH", "CRITICAL"}:
        review_trigger = "recommended-manual"

    return PrePushInspectSummary(
        risk_level=risk_level,
        risk_score=_coerce_int(score_data.get("score"), 0),
        block_review=block_review,
        block_threshold=_coerce_int(score_data.get("block_threshold"), 12),
        risk_reason=str(score_data.get("reason") or ""),
        trigger_factors=_coerce_list(score_data.get("trigger_factors")),
        recommendations=_coerce_list(score_data.get("recommendations")),
        review_trigger=review_trigger,
    )


def render_summary(summary: PrePushInspectSummary) -> str:
    """Render terminal-facing summary text for shell hooks."""
    lines = [
        (
            f"  Risk level: {summary.risk_level} "
            f"(score: {summary.risk_score}/{summary.block_threshold})"
        ),
        f"  Review gate block: {'true' if summary.block_review else 'false'}",
    ]
    if summary.risk_reason:
        lines.append(f"  Risk reason: {summary.risk_reason}")
    if summary.trigger_factors:
        lines.append("  Trigger factors:")
        lines.extend(f"    - {item}" for item in summary.trigger_factors)
    if summary.recommendations:
        lines.append("  Recommendations:")
        lines.extend(f"    - {item}" for item in summary.recommendations)
    return "\n".join(lines)


def _load_payload(stdin: str) -> dict[str, Any]:
    raw = json.loads(stdin)
    if not isinstance(raw, dict):
        return {}
    return raw


def main() -> None:
    """CLI entry for shell hooks."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--field", choices=["review_trigger", "risk_level"])
    args = parser.parse_args()

    payload = _load_payload(sys.stdin.read())
    summary = summarize_inspect_payload(payload)

    if args.field == "review_trigger":
        print(summary.review_trigger)
        return
    if args.field == "risk_level":
        print(summary.risk_level)
        return
    if args.render:
        print(render_summary(summary))
        return
    print(json.dumps(asdict(summary), ensure_ascii=False))


if __name__ == "__main__":
    main()
