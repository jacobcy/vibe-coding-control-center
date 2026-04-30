"""Audit artifact helpers for reviewer role."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

from vibe3.agents.review_parser import ReviewParserError, parse_codex_review
from vibe3.clients.git_client import GitClient
from vibe3.services.artifact_parser import ArtifactParser
from vibe3.services.flow_service import FlowService
from vibe3.services.handoff_service import HandoffService
from vibe3.utils.constants import VERDICT_UNKNOWN
from vibe3.utils.path_helpers import BranchBoundGitClient


@dataclass
class ReviewRunResult:
    """Structured result for command-facing review output."""

    verdict: str
    handoff_file: str | None
    issue_number: int | None


def _create_minimal_audit_artifact(
    content: str,
    verdict: str,
    branch: str | None,
) -> Path:
    artifact_dir = _resolve_minimal_audit_dir(branch)
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    branch_slug = (branch or "detached").replace("/", "-")
    artifact_path = artifact_dir / f"{branch_slug}-audit-auto-{timestamp}.md"
    sanitized_content = ArtifactParser.sanitize_handoff_content(content)
    artifact_path.write_text(
        "# Minimal Review Audit\n\n"
        f"VERDICT: {verdict}\n\n"
        "## Review Output\n\n"
        f"{sanitized_content.rstrip()}\n",
        encoding="utf-8",
    )
    return artifact_path


def _resolve_minimal_audit_dir(branch: str | None) -> Path:
    git = GitClient()
    worktree_root: Path | None = None

    try:
        current_root = git.get_worktree_root()
        if current_root:
            worktree_root = Path(current_root)
    except Exception:
        pass

    if worktree_root is None and branch:
        try:
            worktree_root = git.find_worktree_path_for_branch(branch)
        except Exception:
            pass

    if worktree_root is not None:
        reports_dir = worktree_root / "docs" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        return reports_dir

    reports_dir = Path.cwd() / "docs" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    return reports_dir


def _load_existing_audit_ref(branch: str | None) -> str | None:
    if not branch:
        return None
    flow = FlowService().get_flow_status(branch)
    if flow and flow.audit_ref:
        return flow.audit_ref
    return None


def _resolve_review_verdict(
    review_output: str,
    *,
    audit_ref: str | None = None,
) -> str:
    try:
        review = parse_codex_review(review_output)
        return review.verdict
    except ReviewParserError:
        pass

    if audit_ref:
        audit_path = Path(audit_ref)
        if audit_path.exists():
            try:
                review = parse_codex_review(audit_path.read_text(encoding="utf-8"))
                return review.verdict
            except (OSError, ReviewParserError):
                pass

    return VERDICT_UNKNOWN


def _load_existing_verdict(branch: str | None) -> str | None:
    """Load existing verdict from flow state if agent already wrote it."""
    if not branch:
        return None
    flow = FlowService().get_flow_status(branch)
    if flow and flow.latest_verdict:
        # latest_verdict is already parsed as VerdictRecord by Pydantic
        return flow.latest_verdict.verdict
    return None


def finalize_review_output(
    *,
    review_output: str,
    branch: str | None,
    actor: str,
) -> tuple[str, str]:
    """Finalize review output by confirming audit_ref and writing verdict.

    Skip passive recording if agent already completed both audit_ref and verdict.
    This prevents duplicate handoff_audit events when agent proactively writes.
    """
    existing_audit_ref = _load_existing_audit_ref(branch)
    existing_verdict = _load_existing_verdict(branch)
    reviewer_wrote_audit = bool(existing_audit_ref)
    reviewer_wrote_verdict = bool(existing_verdict)

    # Agent already completed both audit and verdict → skip passive recording entirely
    agent_already_completed = reviewer_wrote_audit and reviewer_wrote_verdict

    if agent_already_completed and existing_audit_ref:
        logger.bind(domain="review", action="finalize").debug(
            "Skipping passive audit recording: agent already completed handoff"
        )
        # existing_verdict is guaranteed non-None when agent_already_completed=True
        assert existing_verdict is not None
        return existing_audit_ref, existing_verdict

    audit_ref: str
    if reviewer_wrote_audit:
        audit_ref = existing_audit_ref  # type: ignore[assignment]
    else:
        audit_ref = str(
            _create_minimal_audit_artifact(
                review_output,
                _resolve_review_verdict(review_output),
                branch,
            )
        )

    if reviewer_wrote_audit:
        audit_path = Path(audit_ref)
        audit_content = None
        if audit_path.exists():
            try:
                audit_content = audit_path.read_text(encoding="utf-8")
            except OSError:
                pass
        verdict = _resolve_review_verdict(
            audit_content or review_output,
            audit_ref=audit_ref,
        )
    else:
        verdict = _resolve_review_verdict(review_output, audit_ref=audit_ref)

    # Only record if agent didn't already complete the handoff
    if not agent_already_completed:
        try:
            handoff_svc = (
                HandoffService(git_client=BranchBoundGitClient(branch))
                if branch
                else HandoffService()
            )
            handoff_svc.record_audit(
                audit_ref=audit_ref,
                actor=actor,
                verdict=verdict,  # type: ignore[arg-type]
                is_system_auto=not reviewer_wrote_audit,
            )
        except Exception as exc:
            logger.bind(domain="review", action="finalize").warning(
                f"Failed to record audit handoff: {exc}"
            )

    return audit_ref, verdict
