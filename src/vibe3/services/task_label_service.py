"""Task label service for vibe-task label operations."""

import json
import subprocess

from loguru import logger

VIBE_TASK_LABEL = "vibe-task"


class TaskLabelService:
    """Service for managing vibe-task labels on issues."""

    def ensure_vibe_task_label(self, issue_number: int) -> bool:
        """Ensure issue has vibe-task label, adding if missing.

        Args:
            issue_number: GitHub issue number

        Returns:
            True if label was added or already present
            False if operation failed
        """
        if self._has_vibe_task_label(issue_number):
            logger.bind(
                external="github",
                operation="ensure_vibe_task_label",
                issue_number=issue_number,
            ).debug("Issue already has vibe-task label")
            return True

        return self._add_vibe_task_label(issue_number)

    def _has_vibe_task_label(self, issue_number: int) -> bool:
        result = subprocess.run(
            ["gh", "issue", "view", str(issue_number), "--json", "labels"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            logger.bind(
                external="github",
                operation="check_vibe_task_label",
                issue_number=issue_number,
                error=result.stderr,
            ).warning("Failed to get issue labels")
            return False

        data = json.loads(result.stdout)
        labels = data.get("labels", [])

        for label in labels:
            if label.get("name") == VIBE_TASK_LABEL:
                return True

        return False

    def _add_vibe_task_label(self, issue_number: int) -> bool:
        result = subprocess.run(
            [
                "gh",
                "issue",
                "edit",
                str(issue_number),
                "--add-label",
                VIBE_TASK_LABEL,
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            logger.bind(
                external="github",
                operation="add_vibe_task_label",
                issue_number=issue_number,
                error=result.stderr,
            ).warning("Failed to add vibe-task label")
            return False

        logger.bind(
            external="github",
            operation="add_vibe_task_label",
            issue_number=issue_number,
        ).info("Added vibe-task label to issue")
        return True
