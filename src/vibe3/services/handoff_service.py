"""Handoff service implementation."""

import os
import subprocess
from pathlib import Path

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.exceptions import SystemError, UserError


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
        """
        git_dir = self.git_client.get_git_dir()
        branch = self.git_client.get_current_branch()

        # Sanitize branch name for directory (replace / with -)
        branch_safe = branch.replace("/", "-").replace("\\", "-")

        handoff_dir = Path(git_dir) / "vibe3" / "handoff" / branch_safe
        handoff_dir.mkdir(parents=True, exist_ok=True)

        return handoff_dir

    def _get_current_handoff_path(self) -> Path:
        """Get path to shared current.md file.

        Returns:
            Path to .git/vibe3/handoff/<branch-safe>/current.md
        """
        return self._get_handoff_dir() / "current.md"

    def ensure_current_handoff(self) -> Path:
        """Ensure shared current.md exists for current branch.

        Creates the file with a minimal template if it doesn't exist.

        Returns:
            Path to the current.md file
        """
        logger.bind(domain="handoff", action="ensure_current_handoff").info(
            "Ensuring handoff file exists"
        )

        handoff_path = self._get_current_handoff_path()

        if not handoff_path.exists():
            # Create minimal template
            template = self._get_handoff_template()
            handoff_path.write_text(template)
            logger.bind(path=str(handoff_path)).success("Created handoff file")
        else:
            logger.bind(path=str(handoff_path)).debug("Handoff file already exists")

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

        content = handoff_path.read_text()
        logger.success("Handoff file read successfully")
        return content

    def open_current_handoff(self, path: Path) -> None:
        """Open shared current.md in editor.

        Args:
            path: Path to the current.md file

        Raises:
            SystemError: If editor cannot be opened
        """
        logger.bind(
            domain="handoff", action="open_current_handoff", path=str(path)
        ).info("Opening handoff file in editor")

        editor = os.environ.get("EDITOR", "vim")

        try:
            subprocess.run([editor, str(path)], check=True)
            logger.success("Editor opened successfully")
        except subprocess.CalledProcessError as e:
            raise SystemError(f"Failed to open editor: {editor}") from e
        except Exception as e:
            raise SystemError(f"Unexpected error opening editor: {e}") from e

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
        logger.bind(
            domain="handoff",
            action="record_plan",
            plan_ref=plan_ref,
            actor=actor,
        ).info("Recording plan handoff")

        branch = self.git_client.get_current_branch()

        # Update flow state only with refs and minimal scene hints
        self.store.update_flow_state(
            branch,
            plan_ref=plan_ref,
            planner_actor=actor,
            latest_actor=actor,
            next_step=next_step,
            blocked_by=blocked_by,
        )

        # Add event
        self.store.add_event(
            branch,
            "handoff_plan",
            actor,
            f"Plan recorded: {plan_ref}",
        )

        logger.success("Plan handoff recorded")

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
        logger.bind(
            domain="handoff",
            action="record_report",
            report_ref=report_ref,
            actor=actor,
        ).info("Recording report handoff")

        branch = self.git_client.get_current_branch()

        # Update flow state
        self.store.update_flow_state(
            branch,
            report_ref=report_ref,
            reviewer_actor=actor,
            latest_actor=actor,
            next_step=next_step,
            blocked_by=blocked_by,
        )

        # Add event
        self.store.add_event(
            branch,
            "handoff_report",
            actor,
            f"Report recorded: {report_ref}",
        )

        logger.success("Report handoff recorded")

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
        logger.bind(
            domain="handoff",
            action="record_audit",
            audit_ref=audit_ref,
            actor=actor,
        ).info("Recording audit handoff")

        branch = self.git_client.get_current_branch()

        # Update flow state
        self.store.update_flow_state(
            branch,
            audit_ref=audit_ref,
            reviewer_actor=actor,
            latest_actor=actor,
            next_step=next_step,
            blocked_by=blocked_by,
        )

        # Add event
        self.store.add_event(
            branch,
            "handoff_audit",
            actor,
            f"Audit recorded: {audit_ref}",
        )

        logger.success("Audit handoff recorded")

    def _get_handoff_template(self) -> str:
        """Get minimal handoff template.

        Returns:
            Template string for new handoff files
        """
        branch = self.git_client.get_current_branch()
        return f"""# Handoff: {branch}

> This is a lightweight handoff file for agent-to-agent communication.
> It is NOT a source of truth - all authoritative data is in the SQLite store.

## Status

- Current actor: unknown
- Next step: TBD
- Blocked by: N/A

## Context

<!-- Add context here -->

## Notes

<!-- Add notes here -->
"""
