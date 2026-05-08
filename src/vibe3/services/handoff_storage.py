"""Handoff storage implementation for filesystem and git operations."""

import shutil
from pathlib import Path

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.utils.git_helpers import get_branch_handoff_dir
from vibe3.utils.git_path_client import GitPathProtocol
from vibe3.utils.path_helpers import get_git_common_dir, normalize_ref_path


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


class HandoffStorage:
    """Handles filesystem operations for handoff records."""

    def __init__(self, git_client: GitPathProtocol | None = None) -> None:
        """Initialize handoff storage.

        Args:
            git_client: GitClient instance for git operations
        """
        self.git_client = git_client or GitClient()

    def get_handoff_dir(self, ensure: bool = True) -> Path:
        """Get handoff directory for current branch.

        Args:
            ensure: If True, create directory if it doesn't exist (idempotent)

        Returns:
            Path to .git/vibe3/handoff/<branch-safe>/

        Raises:
            SystemError: If directory creation fails due to filesystem issues
        """
        git_dir = get_git_common_dir(self.git_client)
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
        """Ensure handoff directory exists for current branch (idempotent)."""
        logger.bind(domain="handoff", action="ensure_handoff_dir").info(
            "Ensuring handoff directory exists"
        )
        return self.get_handoff_dir(ensure=True)

    def ensure_current_handoff(self, force: bool = False) -> Path:
        """Ensure shared current.md exists for current branch."""
        logger.bind(
            domain="handoff", action="ensure_current_handoff", force=force
        ).info("Ensuring handoff file exists")

        # Ensure directory exists (idempotent)
        handoff_dir = self.ensure_handoff_dir()
        branch = self.git_client.get_current_branch()
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
        template = _get_handoff_template(branch)
        handoff_path.write_text(template, encoding="utf-8")
        logger.bind(path=str(handoff_path)).success("Created handoff file")

        return handoff_path

    def read_current_handoff(self) -> str:
        """Read shared current.md content for current branch."""
        logger.bind(domain="handoff", action="read_current_handoff").info(
            "Reading handoff file"
        )

        # Get directory path without creating it
        handoff_dir = self.get_handoff_dir(ensure=False)
        handoff_path = handoff_dir / "current.md"

        if not handoff_path.exists():
            from vibe3.exceptions import UserError

            raise UserError(
                message=f"Handoff file not found: {handoff_path}",
            )

        content = handoff_path.read_text(encoding="utf-8")
        logger.success("Handoff file read successfully")
        return content

    def clear_handoff_for_branch(self, branch: str) -> Path:
        """Delete all handoff files for the given branch."""
        git_dir = self.git_client.get_git_common_dir()
        handoff_dir = get_branch_handoff_dir(git_dir, branch)
        if handoff_dir.exists():
            shutil.rmtree(handoff_dir)
            logger.bind(path=str(handoff_dir), branch=branch).info(
                "Cleared handoff directory for branch"
            )
        return handoff_dir

    def create_artifact(
        self,
        prefix: str,
        content: str | None,
        branch: str | None = None,
    ) -> tuple[str, Path] | None:
        """Create a timestamped handoff artifact file."""
        if branch is None:
            branch = self.git_client.get_current_branch()
            handoff_dir = self.ensure_handoff_dir()
        else:
            git_dir = get_git_common_dir(self.git_client)
            handoff_dir = get_branch_handoff_dir(git_dir, branch)
            handoff_dir.mkdir(parents=True, exist_ok=True)

        from datetime import datetime

        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        artifact_path = handoff_dir / f"{prefix}-{timestamp}.md"

        try:
            if content is not None:
                artifact_path.write_text(content, encoding="utf-8")
            logger.bind(path=str(artifact_path)).success(f"Created {prefix} artifact")
            return branch, artifact_path
        except (PermissionError, OSError) as e:
            logger.bind(path=str(artifact_path)).error(
                f"Failed to create artifact: {e}"
            )
            return None

    def append_current_handoff(
        self,
        message: str,
        actor: str,
        kind: str = "note",
    ) -> Path:
        """Append a lightweight update block to current.md."""
        handoff_path = self.ensure_current_handoff()
        content = handoff_path.read_text(encoding="utf-8")

        from datetime import datetime

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

    def normalize_ref_value(self, ref_value: str, branch: str) -> str:
        """Normalize a reference value (path) relative to branch worktree."""
        return normalize_ref_path(ref_value, branch, self.git_client)
