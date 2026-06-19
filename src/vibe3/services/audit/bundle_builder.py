"""Audit evidence bundle building helpers."""

import hashlib
import socket
from datetime import datetime
from pathlib import Path
from typing import Any

from vibe3.models import (
    CollectionContext,
    EvidenceSummary,
    PrimarySubject,
    RepoInfo,
    SourceRefs,
    TimeWindow,
    Trust,
)


def build_collection_context(
    mode: str,
    source_db: str | None,
    source_commit: str | None,
    time_window: tuple[datetime, datetime] | None = None,
) -> CollectionContext:
    """Build collection context with metadata.

    Args:
        mode: Collection mode
        source_db: Database path
        source_commit: Git commit SHA
        time_window: Optional time window tuple

    Returns:
        CollectionContext object
    """
    time_window_obj = TimeWindow()
    if time_window:
        time_window_obj = TimeWindow(
            start=time_window[0].isoformat(),
            end=time_window[1].isoformat(),
        )

    return CollectionContext(
        mode=mode,  # type: ignore
        source_machine=socket.gethostname(),
        source_db=source_db,
        source_commit=source_commit,
        time_window=time_window_obj,
    )


def build_primary_subject(
    issue_number: int | None = None,
    branch: str | None = None,
) -> PrimarySubject:
    """Build primary subject for bundle.

    Args:
        issue_number: Optional issue number
        branch: Optional branch name

    Returns:
        PrimarySubject object
    """
    return PrimarySubject(
        issue_number=issue_number,
        branch=branch,
        pr_number=None,
    )


def build_source_refs(
    github_refs: list[Any],
    flow_refs: list[Any],
    git_refs: list[Any],
) -> SourceRefs:
    """Build source references container.

    Args:
        github_refs: GitHub references
        flow_refs: Flow references
        git_refs: Git references

    Returns:
        SourceRefs object
    """
    return SourceRefs(
        github=github_refs,
        flow=flow_refs,
        handoff=[],  # Would need separate handoff collection logic
        git=git_refs,
        prompt=[],
        skill=[],
        memory=[],
    )


def build_repo_info() -> RepoInfo:
    """Build repo information.

    Returns:
        RepoInfo object (simplified - would need parsing from repo string or git remote)
    """
    return RepoInfo(
        owner="owner",  # Would need to parse from repo string or git remote
        name="repo",
        local_root=str(Path.cwd()),
    )


def build_summary(
    mode: str,
    flow_refs: list[Any],
    github_refs: list[Any],
    git_refs: list[Any],
) -> EvidenceSummary:
    """Build evidence summary.

    Args:
        mode: Collection mode
        flow_refs: Flow references
        github_refs: GitHub references
        git_refs: Git references

    Returns:
        EvidenceSummary object
    """
    symptom = f"Evidence collected for {mode} mode"
    evidence_text = (
        f"Flow refs: {len(flow_refs)}, "
        f"GitHub refs: {len(github_refs)}, "
        f"Git refs: {len(git_refs)}"
    )
    return EvidenceSummary(
        symptom=symptom,
        evidence_text=evidence_text,
        candidate_failure_patterns=[],
    )


def build_trust(limitations: list[str]) -> Trust:
    """Build trust classification.

    Args:
        limitations: List of collection limitations/errors

    Returns:
        Trust object
    """
    return Trust(
        source_class="authoritative",
        freshness="fresh",
        confidence="medium" if not limitations else "weak",
        limitations=limitations,
    )


def generate_bundle_id(
    mode: str,
    issue_number: int | None = None,
    branch: str | None = None,
) -> str:
    """Generate unique bundle ID.

    Args:
        mode: Collection mode
        issue_number: Optional issue number
        branch: Optional branch name

    Returns:
        16-character bundle ID hash
    """
    bundle_id_data = (
        f"{mode}:{issue_number or ''}:{branch or ''}:{datetime.now().isoformat()}"
    )
    return hashlib.sha256(bundle_id_data.encode()).hexdigest()[:16]
