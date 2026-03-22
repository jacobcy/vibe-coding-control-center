"""Handoff service implementation."""

from datetime import datetime
from pathlib import Path

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.exceptions import UserError
from vibe3.services.handoff_recorder import record_handoff
from vibe3.services.handoff_template import get_handoff_template
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

    def _get_handoff_dir(self) -> Path:
        """Get handoff directory for current branch.

        Returns:
            Path to .git/vibe3/handoff/<branch-safe>/

        Raises:
            SystemError: If directory creation fails due to filesystem issues
        """
        git_dir = self.git_client.get_git_common_dir()
        branch = self.git_client.get_current_branch()

        handoff_dir = get_branch_handoff_dir(git_dir, branch)

        try:
            handoff_dir.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError) as e:
            raise SystemError(
                f"Failed to create handoff directory at {handoff_dir}: {e}"
            ) from e

        return handoff_dir

    def _get_current_handoff_path(self) -> Path:
        """Get path to shared current.md file.

        Returns:
            Path to .git/vibe3/handoff/<branch-safe>/current.md
        """
        return self._get_handoff_dir() / "current.md"

    def ensure_current_handoff(self, force: bool = False) -> Path:
        """Ensure shared current.md exists for current branch.

        Creates the file with a minimal template if it doesn't exist.
        Returns the existing file unchanged unless force=True.

        Args:
            force: Force overwrite if file exists

        Returns:
            Path to the current.md file

        """
        logger.bind(domain="handoff", action="ensure_current_handoff").info(
            "Ensuring handoff file exists"
        )

        handoff_path = self._get_current_handoff_path()

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

        handoff_path = self._get_current_handoff_path()

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
        actor: str,
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
        logger.bind(
            domain="handoff",
            action="append_current_handoff",
            actor=actor,
            kind=kind,
        ).info("Appending handoff update")

        handoff_path = self.ensure_current_handoff()
        content = handoff_path.read_text(encoding="utf-8")
        timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
        update_block = f"### {timestamp} | {actor} | {kind}\n{message}\n"

        updates_heading = "## Updates\n"
        if updates_heading in content:
            updated = content.rstrip() + "\n\n" + update_block
        else:
            updated = content.rstrip() + "\n\n" + updates_heading + "\n" + update_block

        handoff_path.write_text(updated.rstrip() + "\n", encoding="utf-8")
        logger.bind(path=str(handoff_path)).success("Appended handoff update")
        return handoff_path

    def record_plan(
        self,
        plan_ref: str,
        next_step: str | None,
        blocked_by: str | None,
        actor: str,
    ) -> None:
        """Record plan handoff.

        Args:
            plan_ref: Plan document reference
            next_step: Next step suggestion
            blocked_by: Blocker description
            actor: Actor identifier
        """
        record_handoff(
            self.store, self.git_client, "plan", plan_ref, next_step, blocked_by, actor
        )

    def record_report(
        self,
        report_ref: str,
        next_step: str | None,
        blocked_by: str | None,
        actor: str,
    ) -> None:
        """Record report handoff.

        Args:
            report_ref: Report document reference
            next_step: Next step suggestion
            blocked_by: Blocker description
            actor: Actor identifier
        """
        record_handoff(
            self.store,
            self.git_client,
            "report",
            report_ref,
            next_step,
            blocked_by,
            actor,
        )

    def record_audit(
        self,
        audit_ref: str,
        next_step: str | None,
        blocked_by: str | None,
        actor: str,
    ) -> None:
        """Record audit handoff.

        Args:
            audit_ref: Audit document reference
            next_step: Next step suggestion
            blocked_by: Blocker description
            actor: Actor identifier
        """
        record_handoff(
            self.store,
            self.git_client,
            "audit",
            audit_ref,
            next_step,
            blocked_by,
            actor,
        )

    def _get_handoff_template(self) -> str:
        """Get minimal handoff template.

        Returns:
            Template string for new handoff files
        """
        branch = self.git_client.get_current_branch()
        return get_handoff_template(branch)
