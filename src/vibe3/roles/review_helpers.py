"""Audit artifact helpers for reviewer role."""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from vibe3.services.flow_service import FlowService
from vibe3.utils.constants import VERDICT_UNKNOWN


@dataclass
class ReviewRunResult:
    """Structured result for command-facing review output."""

    verdict: str
    handoff_file: str | None
    issue_number: int | None


def _load_existing_audit_ref(branch: str | None) -> str | None:
    if not branch:
        return None
    flow = FlowService().get_flow_status(branch)
    if flow and flow.audit_ref:
        return flow.audit_ref
    return None


def _load_existing_verdict(branch: str | None) -> str | None:
    """Load existing verdict from flow state if agent already wrote it."""
    if not branch:
        return None
    flow = FlowService().get_flow_status(branch)
    if flow and flow.latest_verdict:
        return flow.latest_verdict.verdict
    return None


def finalize_review_output(
    *,
    review_output: str,
    branch: str | None,
    actor: str,
) -> tuple[str, str]:
    """Read audit_ref and verdict from flow state after review completes.

    This is a pure passive reader — it does NOT parse review output for
    verdict, create audit artifacts, or call record_audit.  The agent is
    responsible for writing verdict and audit via handoff commands during
    execution.  If the agent didn't write them, we return empty/unknown
    values and let the downstream gate handle the noop case.
    """
    _ = review_output  # kept for signature compatibility; no longer parsed
    _ = actor

    audit_ref = _load_existing_audit_ref(branch) or ""
    verdict = _load_existing_verdict(branch) or VERDICT_UNKNOWN

    logger.bind(domain="review", action="finalize").debug(
        "Passive review finalize: audit_ref={!r}, verdict={!r}",
        audit_ref,
        verdict,
    )

    return audit_ref, verdict
