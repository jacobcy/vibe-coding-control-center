"""Unified handoff recording for plan/run/review agent commands."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from vibe3.models.review_runner import AgentOptions
from vibe3.services.handoff_event_service import (
    create_handoff_artifact,
    persist_handoff_event,
)
from vibe3.services.review_runner import (
    format_agent_actor,
    resolve_actor_backend_model,
)

HandoffKind = Literal["plan", "run", "review"]

_ACTOR_ROLE_BY_KIND: dict[HandoffKind, str] = {
    "plan": "planner_actor",
    "run": "executor_actor",
    "review": "reviewer_actor",
}

_SESSION_ROLE_BY_KIND: dict[HandoffKind, str] = {
    "plan": "planner_session_id",
    "run": "executor_session_id",
    "review": "reviewer_session_id",
}

_REF_FIELD_BY_KIND: dict[HandoffKind, str] = {
    "plan": "plan_ref",
    "run": "report_ref",
    "review": "audit_ref",
}

_RESERVED_REF_KEYS = {
    "ref",
    "backend",
    "model",
    "session_id",
    "modified_files",
    "modified_count",
    "verdict",
}


@dataclass(frozen=True)
class HandoffRecord:
    """Generic handoff record for all agent command artifacts."""

    kind: HandoffKind
    content: str
    options: AgentOptions
    session_id: str | None = None
    metadata: dict[str, str] | None = None


def parse_modified_files(content: str) -> list[str]:
    """Extract modified files from a run artifact body."""

    match = re.search(
        r"### Modified Files\s*([\s\S]*?)(?:\n###|\Z)",
        content,
        re.IGNORECASE,
    )
    if not match:
        return []

    files_section = match.group(1)
    file_matches = re.findall(
        r"^-\s*([^:\]]+)(?::|\])?",
        files_section,
        re.MULTILINE,
    )
    return [path.strip() for path in file_matches if path.strip()]


def parse_review_verdict(content: str) -> str | None:
    """Extract verdict token from review content."""

    match = re.search(r"VERDICT:\s*(PASS|FAIL|BLOCK)", content, re.IGNORECASE)
    return match.group(1).upper() if match else None


def _build_detail(record: HandoffRecord, artifact_file: Path) -> tuple[str, dict[str, str]]:
    refs: dict[str, str] = {}
    detail_parts = [f"{record.kind.capitalize()} completed: {artifact_file.name}"]

    metadata = record.metadata or {}

    if record.kind == "run":
        modified_files = parse_modified_files(record.content)
        if modified_files:
            refs["modified_files"] = ",".join(modified_files)
            refs["modified_count"] = str(len(modified_files))
            detail_parts.append(f"Modified {len(modified_files)} files:")
            for file_path in modified_files[:3]:
                detail_parts.append(f"  - {file_path}")
            if len(modified_files) > 3:
                detail_parts.append(f"  ... and {len(modified_files) - 3} more")

    if record.kind == "review":
        verdict = metadata.get("verdict") or parse_review_verdict(record.content)
        if verdict:
            refs["verdict"] = verdict
            comment_count = metadata.get("comment_count")
            if comment_count:
                detail_parts.append(f"Verdict: {verdict}, {comment_count} comments")
            else:
                detail_parts.append(f"Verdict: {verdict}")

    for key, value in metadata.items():
        if key != "comment_count" and key not in _RESERVED_REF_KEYS:
            refs[key] = value

    return "\n".join(detail_parts), refs


def record_handoff_unified(record: HandoffRecord) -> Path | None:
    """Persist a plan/run/review artifact and corresponding handoff event."""

    artifact = create_handoff_artifact(record.kind, record.content)
    if artifact is None:
        return None

    branch, artifact_file = artifact
    actor = format_agent_actor(record.options)
    backend, model = resolve_actor_backend_model(record.options)

    detail, derived_refs = _build_detail(record, artifact_file)
    refs: dict[str, str] = {
        "ref": str(artifact_file),
        "backend": backend,
        **derived_refs,
    }
    if model:
        refs["model"] = model
    if record.session_id:
        refs["session_id"] = record.session_id

    flow_state_updates: dict[str, object] = {
        _REF_FIELD_BY_KIND[record.kind]: str(artifact_file),
        _ACTOR_ROLE_BY_KIND[record.kind]: actor,
        _SESSION_ROLE_BY_KIND[record.kind]: record.session_id,
    }

    persist_handoff_event(
        branch=branch,
        event_type=f"handoff_{record.kind}",
        actor=actor,
        detail=detail,
        refs=refs,
        flow_state_updates=flow_state_updates,
    )

    return artifact_file