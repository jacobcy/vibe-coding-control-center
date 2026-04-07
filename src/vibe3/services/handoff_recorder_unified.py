"""Unified handoff recording for plan/run/review agent commands."""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal, Protocol

from vibe3.agents.review_runner import (
    format_agent_actor,
    resolve_actor_backend_model,
)
from vibe3.clients.git_client import GitClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.models.review_runner import AgentOptions
from vibe3.services.handoff_service import HandoffService
from vibe3.services.signature_service import SignatureService


class _BranchBoundGitClientProtocol(Protocol):
    """Protocol for git client operations needed by HandoffService."""

    def get_current_branch(self) -> str: ...
    def get_git_common_dir(self) -> str: ...


class _BranchBoundGitClient:
    """Git client shim that pins handoff artifact writes to a target branch."""

    def __init__(self, branch: str) -> None:
        self._branch = branch
        self._delegate = GitClient()

    def get_current_branch(self) -> str:
        return self._branch

    def get_git_common_dir(self) -> str:
        return self._delegate.get_git_common_dir()


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


# ---------------------------------------------------------------------------
# Handoff artifact & event helpers (inlined from handoff_event_service)
# ---------------------------------------------------------------------------


def create_handoff_artifact(
    prefix: str,
    content: str | None,
    branch: str | None = None,
) -> tuple[str, Path] | None:
    """Create a timestamped handoff artifact file for current branch.

    Uses HandoffService.ensure_handoff_dir() as unified entry point
    for directory creation (idempotent).

    Returns:
        tuple(branch, file_path) when branch is available, else None.
    """
    if branch is None:
        git = GitClient()
        try:
            branch = git.get_current_branch()
        except Exception:
            return None
        handoff_service = HandoffService(git_client=git)
    else:
        handoff_service = HandoffService(git_client=_BranchBoundGitClient(branch))

    handoff_dir = handoff_service.ensure_handoff_dir()

    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    artifact_path = handoff_dir / f"{prefix}-{timestamp}.md"
    if content is not None:
        artifact_path.write_text(content, encoding="utf-8")

    return branch, artifact_path


def persist_handoff_event(
    branch: str,
    event_type: str,
    actor: str,
    detail: str,
    refs: dict[str, str],
    flow_state_updates: dict[str, object] | None = None,
) -> None:
    """Persist handoff event and optional flow-state updates."""
    store = SQLiteClient()
    store.add_event(branch, event_type, actor, detail=detail, refs=refs)
    if flow_state_updates:
        store.update_flow_state(branch, **flow_state_updates)


@dataclass(frozen=True)
class HandoffRecord:
    """Generic handoff record for all agent command artifacts."""

    kind: HandoffKind
    content: str
    options: AgentOptions
    session_id: str | None = None
    metadata: dict[str, str] | None = None
    branch: str | None = None


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
    artifact = create_handoff_artifact(
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

    flow_state_updates: dict[str, object] = {
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
