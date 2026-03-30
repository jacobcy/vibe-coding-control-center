"""Handoff service implementation."""

from datetime import datetime
from pathlib import Path

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.exceptions import UserError
from vibe3.services.signature_service import SignatureService
from vibe3.utils.git_helpers import get_branch_handoff_dir


class HandoffService:
    """Service for managing handoff records."""

    def __init__(
        self,
        store: SQLiteClient | None = None,
        git_client: GitClient | None = None,
    ) -> None:
        """Initialize handoff service.

        Args:
            store: SQLiteClient instance for persistence
            git_client: GitClient instance for git operations
        """
        self.store = store or SQLiteClient()
        self.git_client = git_client or GitClient()

    def _get_handoff_dir(self, ensure: bool = True) -> Path:
        """Get handoff directory for current branch.

        Args:
            ensure: If True, create directory if it doesn't exist (idempotent)

        Returns:
            Path to .git/vibe3/handoff/<branch-safe>/

        Raises:
            SystemError: If directory creation fails due to filesystem issues
        """
        git_dir = self.git_client.get_git_common_dir()
        branch = self.git_client.get_current_branch()

        handoff_dir = get_branch_handoff_dir(git_dir, branch)

        if ensure:
            try:
                handoff_dir.mkdir(parents=True, exist_ok=True)
            except (PermissionError, OSError) as e:
                raise SystemError(
                    f"Failed to create handoff directory at {handoff_dir}: {e}"
                ) from e

        return handoff_dir

    def ensure_handoff_dir(self) -> Path:
        """Ensure handoff directory exists for current branch (idempotent).

        This is the unified entry point for all handoff directory creation.
        Safe to call multiple times - will only create if doesn't exist.

        Returns:
            Path to the handoff directory

        Example:
            >>> service = HandoffService()
            >>> handoff_dir = service.ensure_handoff_dir()
            >>> # Directory now exists, can write files to it
        """
        logger.bind(domain="handoff", action="ensure_handoff_dir").info(
            "Ensuring handoff directory exists"
        )
        return self._get_handoff_dir(ensure=True)

    def ensure_current_handoff(self, force: bool = False) -> Path:
        """Ensure shared current.md exists for current branch.

        Creates the file with a minimal template if it doesn't exist.
        Returns the existing file unchanged unless force=True.

        This method is idempotent - safe to call multiple times.

        Args:
            force: Force overwrite if file exists

        Returns:
            Path to the current.md file

        """
        logger.bind(
            domain="handoff", action="ensure_current_handoff", force=force
        ).info("Ensuring handoff file exists")

        # Ensure directory exists (idempotent)
        handoff_dir = self.ensure_handoff_dir()
        handoff_path = handoff_dir / "current.md"

        if handoff_path.exists():
            if not force:
                logger.bind(path=str(handoff_path)).info(
                    "Handoff file already exists, returning existing file"
                )
                return handoff_path
            # Force overwrite
            logger.bind(path=str(handoff_path)).info(
                "Overwriting existing handoff file"
            )

        # Create minimal template
        template = self._get_handoff_template()
        handoff_path.write_text(template, encoding="utf-8")
        logger.bind(path=str(handoff_path)).success("Created handoff file")

        return handoff_path

    def read_current_handoff(self) -> str:
        """Read shared current.md content for current branch.

        Returns:
            Content of current.md file

        Raises:
            UserError: If current.md doesn't exist
        """
        logger.bind(domain="handoff", action="read_current_handoff").info(
            "Reading handoff file"
        )

        # Get directory path without creating it
        handoff_dir = self._get_handoff_dir(ensure=False)
        handoff_path = handoff_dir / "current.md"

        if not handoff_path.exists():
            raise UserError(
                message=f"Handoff file not found: {handoff_path}",
            )

        content = handoff_path.read_text(encoding="utf-8")
        logger.success("Handoff file read successfully")
        return content

    def append_current_handoff(
        self,
        message: str,
        actor: str | None,
        kind: str = "note",
    ) -> Path:
        """Append a lightweight update block to current.md.

        Args:
            message: Human-readable update message
            actor: Actor identifier
            kind: Lightweight update kind, such as finding/blocker/next/note

        Returns:
            Path to the current.md file
        """
        branch = self.git_client.get_current_branch()
        effective_actor = SignatureService.resolve_for_branch(
            self.store,
            branch,
            explicit_actor=actor,
        )
        logger.bind(
            domain="handoff",
            action="append_current_handoff",
            actor=effective_actor,
            kind=kind,
        ).info("Appending handoff update")

        handoff_path = self.ensure_current_handoff()
        content = handoff_path.read_text(encoding="utf-8")
        timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
        update_block = f"### {timestamp} | {effective_actor} | {kind}\n{message}\n"

        updates_heading = "## Updates\n"
        if updates_heading in content:
            updated = content.rstrip() + "\n\n" + update_block
        else:
            updated = content.rstrip() + "\n\n" + updates_heading + "\n" + update_block

        handoff_path.write_text(updated.rstrip() + "\n", encoding="utf-8")
        logger.bind(path=str(handoff_path)).success("Appended handoff update")
        return handoff_path

    def _record_item(
        self,
        kind: str,
        ref: str,
        next_step: str | None,
        blocked_by: str | None,
        actor: str | None,
        session_id: str | None = None,
    ) -> None:
        """Helper to record a handoff item."""
        branch = self.git_client.get_current_branch()
        effective_actor = SignatureService.resolve_for_branch(
            self.store,
            branch,
            explicit_actor=actor,
        )
        _record_handoff(
            self.store,
            self.git_client,
            kind,
            ref,
            next_step,
            blocked_by,
            effective_actor,
            session_id=session_id,
        )

    def record_plan(
        self,
        plan_ref: str,
        next_step: str | None,
        blocked_by: str | None,
        actor: str | None,
        session_id: str | None = None,
    ) -> None:
        """Record plan handoff."""
        self._record_item(
            "plan", plan_ref, next_step, blocked_by, actor, session_id=session_id
        )

    def record_report(
        self,
        report_ref: str,
        next_step: str | None,
        blocked_by: str | None,
        actor: str | None,
        session_id: str | None = None,
    ) -> None:
        """Record report handoff."""
        self._record_item(
            "report", report_ref, next_step, blocked_by, actor, session_id=session_id
        )

    def record_audit(
        self,
        audit_ref: str,
        next_step: str | None,
        blocked_by: str | None,
        actor: str | None,
        session_id: str | None = None,
    ) -> None:
        """Record audit handoff."""
        self._record_item(
            "audit", audit_ref, next_step, blocked_by, actor, session_id=session_id
        )

    def _get_handoff_template(self) -> str:
        """Get minimal handoff template.

        Returns:
            Template string for new handoff files
        """
        branch = self.git_client.get_current_branch()
        return _get_handoff_template(branch)


# ---------------------------------------------------------------------------
# Template generation (from handoff_template.py)
# ---------------------------------------------------------------------------


def _get_handoff_template(branch: str) -> str:
    """Get minimal handoff template."""
    return f"""# Handoff: {branch}

> This is a lightweight handoff file for agent-to-agent communication.
> It is NOT a source of truth - all authoritative data is in the SQLite store.

## Meta

- Branch: {branch}
- Updated at: TBD
- Latest actor: unknown

## Summary

<!-- Brief summary of current state -->

## Findings

<!-- Open findings and observations -->

## Blockers

<!-- Current blockers -->

## Next Actions

<!-- Suggested next actions -->

## Key Files

<!-- Important files for the next agent -->

## Evidence Refs

<!-- Links to plans, reports, PRs, issues, or logs -->

## Updates

<!-- Append-only lightweight updates -->
"""


# ---------------------------------------------------------------------------
# Handoff recording (from handoff_recorder.py)
# ---------------------------------------------------------------------------


def _record_handoff(
    store: SQLiteClient,
    git_client: GitClient,
    handoff_type: str,
    ref: str,
    next_step: str | None,
    blocked_by: str | None,
    actor: str,
    session_id: str | None = None,
) -> None:
    """Record handoff to store."""
    logger.bind(
        domain="handoff",
        action=f"record_{handoff_type}",
        ref=ref,
        actor=actor,
        session_id=session_id,
    ).info(f"Recording {handoff_type} handoff")

    branch = git_client.get_current_branch()

    # Determine actor role and session role based on handoff type
    if handoff_type == "plan":
        actor_role = "planner_actor"
        session_role = "planner_session_id"
    elif handoff_type == "report":
        actor_role = "executor_actor"
        session_role = "executor_session_id"
    else:  # audit
        actor_role = "reviewer_actor"
        session_role = "reviewer_session_id"

    # Build update kwargs
    update_kwargs: dict[str, object] = {
        actor_role: actor,
        "next_step": next_step,
        "blocked_by": blocked_by,
    }

    if session_id:
        update_kwargs[session_role] = session_id

    # Set the appropriate ref field
    if handoff_type == "plan":
        update_kwargs["plan_ref"] = ref
    elif handoff_type == "report":
        update_kwargs["report_ref"] = ref
    else:
        update_kwargs["audit_ref"] = ref

    # Update flow state
    store.update_flow_state(branch, **update_kwargs)

    # Add event
    store.add_event(
        branch,
        f"handoff_{handoff_type}",
        actor,
        f"{handoff_type.capitalize()} recorded: {ref}",
    )

    logger.success(f"{handoff_type.capitalize()} handoff recorded")
