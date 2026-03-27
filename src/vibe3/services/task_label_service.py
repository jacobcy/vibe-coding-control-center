"""Task label service for vibe-task label operations."""

from vibe3.services.label_service import VIBE_TASK_LABEL, LabelService


class TaskLabelService:
    """Service for managing vibe-task labels on issues."""

    def __init__(self, label_service: LabelService | None = None) -> None:
        self.label_service = label_service or LabelService()

    def ensure_vibe_task_label(self, issue_number: int) -> bool:
        """Ensure issue has vibe-task label, adding if missing.

        Args:
            issue_number: GitHub issue number

        Returns:
            True if label was added or already present
            False if operation failed
        """
        status = self.label_service.confirm_vibe_task(issue_number, should_exist=True)
        return status != "blocked"

    def _has_vibe_task_label(self, issue_number: int) -> bool:
        return self.label_service.has_label(issue_number, VIBE_TASK_LABEL)

    def _add_vibe_task_label(self, issue_number: int) -> bool:
        status = self.label_service.confirm_vibe_task(issue_number, should_exist=True)
        return status in {"confirmed", "advanced"}
