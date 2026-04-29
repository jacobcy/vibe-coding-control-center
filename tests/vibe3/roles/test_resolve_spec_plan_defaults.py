"""Tests for resolve_spec_plan_input default spec_ref logic."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.roles.plan import resolve_spec_plan_input


class TestResolveSpecPlanInputDefaultSpecRef:
    """Tests for resolve_spec_plan_input using flow's spec_ref as default."""

    def test_explicit_file_works(self, tmp_path: Path) -> None:
        """Explicit --file should work normally."""
        spec_file = tmp_path / "explicit-spec.md"
        spec_file.write_text("Explicit spec content", encoding="utf-8")

        # Explicit file input never queries flow
        result = resolve_spec_plan_input("test-branch", file=spec_file)

        assert result.description == "Explicit spec content"
        assert result.spec_path == str(spec_file.resolve())

    def test_no_explicit_input_uses_flow_spec_ref_file(self, tmp_path: Path) -> None:
        """When no --file or --msg, use flow.spec_ref (file type)."""
        spec_file = tmp_path / "flow-spec.md"
        spec_file.write_text("Flow spec content", encoding="utf-8")

        # Mock flow with file spec_ref
        mock_flow = MagicMock()
        mock_flow.spec_ref = str(spec_file)

        # Mock spec service
        mock_spec_info = MagicMock()
        mock_spec_info.kind = "file"
        mock_spec_info.file_path = str(spec_file)

        # Patch at the source module, not where it's imported
        with (
            patch("vibe3.services.flow_service.FlowService") as mock_fs,
            patch("vibe3.services.spec_ref_service.SpecRefService") as mock_ss,
        ):
            mock_fs.return_value.get_flow_status.return_value = mock_flow
            mock_ss.return_value.parse_spec_ref.return_value = mock_spec_info
            mock_ss.return_value.validate_spec_ref.return_value = (True, "")
            mock_ss.return_value.get_spec_content_for_prompt.return_value = (
                "Flow spec content"
            )

            result = resolve_spec_plan_input("test-branch")

        assert result.description == "Flow spec content"
        assert result.spec_path == str(spec_file)

    def test_no_explicit_input_uses_flow_spec_ref_issue(self) -> None:
        """When no --file or --msg, use flow.spec_ref (issue type)."""
        # Mock flow with issue spec_ref
        mock_flow = MagicMock()
        mock_flow.spec_ref = "#789"

        # Mock spec service
        mock_spec_info = MagicMock()
        mock_spec_info.kind = "issue"
        mock_spec_info.issue_number = 789
        mock_spec_info.file_path = None

        # Patch at the source module
        with (
            patch("vibe3.services.flow_service.FlowService") as mock_fs,
            patch("vibe3.services.spec_ref_service.SpecRefService") as mock_ss,
        ):
            mock_fs.return_value.get_flow_status.return_value = mock_flow
            mock_ss.return_value.parse_spec_ref.return_value = mock_spec_info
            mock_ss.return_value.validate_spec_ref.return_value = (True, "")
            content = "Issue #789: Add feature\nBody content"
            mock_ss.return_value.get_spec_content_for_prompt.return_value = content

            result = resolve_spec_plan_input("test-branch")

        assert "Issue #789" in result.description
        assert result.spec_path is None

    def test_no_explicit_input_raises_when_no_flow_spec_ref(self) -> None:
        """Raise ValueError when no explicit input and flow has no spec_ref."""
        mock_flow = MagicMock()
        mock_flow.spec_ref = None

        # Patch at the source module
        with patch("vibe3.services.flow_service.FlowService") as mock_fs:
            mock_fs.return_value.get_flow_status.return_value = mock_flow

            with pytest.raises(ValueError) as exc_info:
                resolve_spec_plan_input("test-branch")

        assert "No spec provided" in str(exc_info.value)

    def test_no_explicit_input_raises_when_no_flow(self) -> None:
        """Raise ValueError when flow does not exist."""
        # Patch at the source module
        with patch("vibe3.services.flow_service.FlowService") as mock_fs:
            mock_fs.return_value.get_flow_status.return_value = None

            with pytest.raises(ValueError) as exc_info:
                resolve_spec_plan_input("test-branch")

        assert "No spec provided" in str(exc_info.value)

    def test_no_explicit_input_raises_when_flow_spec_ref_invalid(self) -> None:
        """Raise ValueError when flow.spec_ref is invalid."""
        mock_flow = MagicMock()
        mock_flow.spec_ref = "nonexistent.md"

        # Patch at the source module
        with (
            patch("vibe3.services.flow_service.FlowService") as mock_fs,
            patch("vibe3.services.spec_ref_service.SpecRefService") as mock_ss,
        ):
            mock_fs.return_value.get_flow_status.return_value = mock_flow
            mock_ss.return_value.validate_spec_ref.return_value = (
                False,
                "File not found",
            )

            with pytest.raises(ValueError) as exc_info:
                resolve_spec_plan_input("test-branch")

        assert "Flow spec_ref invalid" in str(exc_info.value)

    def test_no_explicit_input_raises_when_flow_spec_content_unreadable(self) -> None:
        """Raise ValueError when flow.spec_ref content cannot be read."""
        mock_flow = MagicMock()
        mock_flow.spec_ref = "#999"

        # Patch at the source module
        with (
            patch("vibe3.services.flow_service.FlowService") as mock_fs,
            patch("vibe3.services.spec_ref_service.SpecRefService") as mock_ss,
        ):
            mock_fs.return_value.get_flow_status.return_value = mock_flow
            mock_ss.return_value.validate_spec_ref.return_value = (True, "")
            mock_ss.return_value.get_spec_content_for_prompt.return_value = None

            with pytest.raises(ValueError) as exc_info:
                resolve_spec_plan_input("test-branch")

        assert "Failed to read spec content" in str(exc_info.value)
