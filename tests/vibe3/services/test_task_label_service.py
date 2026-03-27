"""Tests for TaskLabelService."""

from unittest.mock import MagicMock, patch

from vibe3.services.task_label_service import TaskLabelService


class TestTaskLabelService:
    """Tests for vibe-task label operations."""

    @patch("vibe3.services.task_label_service.LabelService")
    def test_ensure_vibe_task_label_already_present(
        self, mock_label_service_cls: MagicMock
    ) -> None:
        """When label already present, should return True without adding."""
        mock_label_service_cls.return_value.confirm_vibe_task.return_value = "confirmed"

        svc = TaskLabelService()
        result = svc.ensure_vibe_task_label(123)

        assert result is True
        mock_label_service_cls.return_value.confirm_vibe_task.assert_called_once_with(
            123, should_exist=True
        )

    @patch("vibe3.services.task_label_service.LabelService")
    def test_ensure_vibe_task_label_adds_when_missing(
        self, mock_label_service_cls: MagicMock
    ) -> None:
        """When label missing, should add it and return True."""
        mock_label_service_cls.return_value.confirm_vibe_task.return_value = "advanced"

        svc = TaskLabelService()
        result = svc.ensure_vibe_task_label(123)

        assert result is True

    @patch("vibe3.services.task_label_service.LabelService")
    def test_ensure_vibe_task_label_handles_failure(
        self, mock_label_service_cls: MagicMock
    ) -> None:
        """When label operation is blocked, should return False."""
        mock_label_service_cls.return_value.confirm_vibe_task.return_value = "blocked"

        svc = TaskLabelService()
        result = svc.ensure_vibe_task_label(123)

        assert result is False

    @patch("vibe3.services.task_label_service.LabelService")
    def test_has_vibe_task_label_returns_true(
        self, mock_label_service_cls: MagicMock
    ) -> None:
        """Should return True when vibe-task label exists."""
        mock_label_service_cls.return_value.has_label.return_value = True

        svc = TaskLabelService()
        result = svc._has_vibe_task_label(123)

        assert result is True
        mock_label_service_cls.return_value.has_label.assert_called_once_with(
            123, "vibe-task"
        )

    @patch("vibe3.services.task_label_service.LabelService")
    def test_has_vibe_task_label_returns_false(
        self, mock_label_service_cls: MagicMock
    ) -> None:
        """Should return False when vibe-task label does not exist."""
        mock_label_service_cls.return_value.has_label.return_value = False

        svc = TaskLabelService()
        result = svc._has_vibe_task_label(123)

        assert result is False
