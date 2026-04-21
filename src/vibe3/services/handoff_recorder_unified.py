"""Unified handoff recording for plan/run/review agent commands."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from vibe3.agents.backends.async_launcher import resolve_async_log_path
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.execution.actor_support import (
    format_agent_actor,
    resolve_actor_backend_model,
)
from vibe3.execution.role_policy import get_kind_actor_key
from vibe3.models.review_runner import AgentOptions
from vibe3.services.handoff_service import HandoffService
from vibe3.services.signature_service import SignatureService

HandoffKind = Literal["plan", "run", "review"]

_RESERVED_REF_KEYS = {
    "ref",
    "backend",
    "model",
    "session_id",
    "modified_files",
    "modified_count",
    "verdict",
}

_AGENT_PROMPT_BLOCK_RE = re.compile(r"<agent-prompt>.*?</agent-prompt>\s*", re.DOTALL)


@dataclass(frozen=True)
class HandoffRecord:
    """Generic handoff record for all agent command artifacts."""

    kind: HandoffKind
    content: str
    options: AgentOptions
    session_id: str | None = None
    metadata: dict[str, str] | None = None
    branch: str | None = None
    log_path: str | None = None


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

    match = re.search(r"VERDICT:\s*(PASS|MAJOR|BLOCK)", content, re.IGNORECASE)
    return match.group(1).upper() if match else None


def sanitize_handoff_content(content: str) -> str:
    """Strip prompt-provenance blocks from persisted shared artifacts."""
    return _AGENT_PROMPT_BLOCK_RE.sub("", content)


def _build_detail(
    record: HandoffRecord, artifact_file: Path
) -> tuple[str, dict[str, str]]:
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
        verdict = parse_review_verdict(record.content) or metadata.get("verdict")
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

    sanitized_content = sanitize_handoff_content(record.content)
    handoff_service = HandoffService()
    artifact = handoff_service.create_artifact(
        record.kind,
        sanitized_content,
        branch=record.branch,
    )
    if artifact is None:
        return None

    branch, artifact_file = artifact
    actor = SignatureService.resolve_for_branch(
        SQLiteClient(),
        branch,
        explicit_actor=format_agent_actor(record.options),
    )
    backend, model = resolve_actor_backend_model(record.options)

    sanitized_record = HandoffRecord(
        kind=record.kind,
        content=sanitized_content,
        options=record.options,
        session_id=record.session_id,
        metadata=record.metadata,
        branch=record.branch,
        log_path=record.log_path,
    )

    detail, derived_refs = _build_detail(sanitized_record, artifact_file)
    refs: dict[str, str] = {
        "ref": str(artifact_file),
        "backend": backend,
        **derived_refs,
    }
    if model:
        refs["model"] = model
    if record.session_id:
        refs["session_id"] = record.session_id

    # Add log_path to refs if available
    # Either use explicit log_path or infer from session_id
    if record.log_path:
        refs["log_path"] = record.log_path
    elif record.session_id:
        # Infer log_path from session_id pattern
        log_dir = Path(__file__).resolve().parents[3] / "temp" / "logs"
        inferred_log_path = resolve_async_log_path(log_dir, record.session_id)
        refs["log_path"] = str(inferred_log_path)

    flow_state_updates: dict[str, object] = {
        get_kind_actor_key(record.kind): actor,
    }

    handoff_service.persist_artifact_event(
        branch=branch,
        event_type=f"handoff_{record.kind}",
        actor=actor,
        detail=detail,
        refs=refs,
        flow_state_updates=flow_state_updates,
    )

    return artifact_file
