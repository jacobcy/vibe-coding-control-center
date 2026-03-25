"""Shared helpers for handoff artifact files and event persistence."""

from datetime import datetime
from pathlib import Path

from vibe3.clients.git_client import GitClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.services.handoff_service import HandoffService


def create_handoff_artifact(
    prefix: str,
    content: str | None,
) -> tuple[str, Path] | None:
    """Create a timestamped handoff artifact file for current branch.

    Uses HandoffService.ensure_handoff_dir() as unified entry point
    for directory creation (idempotent).

    Returns:
        tuple(branch, file_path) when branch is available, else None.
    """
    git = GitClient()
    try:
        branch = git.get_current_branch()
    except Exception:
        return None

    # Use unified entry point for directory creation (idempotent)
    handoff_service = HandoffService()
    handoff_dir = handoff_service._get_handoff_dir()

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
