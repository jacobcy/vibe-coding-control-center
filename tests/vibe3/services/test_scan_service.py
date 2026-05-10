"""Tests for scan service functions."""

from vibe3.services.scan_service import (
    extract_material_description,
    fetch_supervisor_candidates,
    render_governance_prompt_preview,
)


class TestExtractMaterialDescription:
    """Tests for material description extraction."""

    def test_extracts_title_from_markdown(self, tmp_path):
        """Test extracting title from markdown file."""
        # Create temp markdown file
        md_file = tmp_path / "test-material.md"
        md_file.write_text("# Test Material 治理材料\n\nSome content\n")

        description = extract_material_description(str(md_file))
        assert description == "Test Material 治理材料"

    def test_fallback_to_filename_without_title(self, tmp_path):
        """Test fallback to filename when no title."""
        md_file = tmp_path / "no-title.md"
        md_file.write_text("Some content without title\n")

        description = extract_material_description(str(md_file))
        assert "no-title.md" in description

    def test_handles_missing_file(self):
        """Test handling of missing file."""
        description = extract_material_description("nonexistent/file.md")
        assert "nonexistent" in description or "file.md" in description


class TestFetchSupervisorCandidates:
    """Tests for supervisor candidate fetching."""

    def test_filters_by_labels(self):
        """Test filtering issues by supervisor + state/handoff labels."""
        from unittest.mock import MagicMock

        mock_github = MagicMock()
        mock_github.list_issues.return_value = [
            {
                "number": 123,
                "title": "Test Issue",
                "labels": [{"name": "supervisor"}, {"name": "state/handoff"}],
            },
            {
                "number": 456,
                "title": "No Handoff",
                "labels": [{"name": "supervisor"}],
            },
        ]

        candidates = fetch_supervisor_candidates(mock_github, "owner/repo")

        # Should only return issue with both labels
        assert len(candidates) == 1
        assert candidates[0]["number"] == 123

    def test_returns_empty_list_on_error(self):
        """Test returns empty list on GitHub error."""
        from unittest.mock import MagicMock

        mock_github = MagicMock()
        mock_github.list_issues.side_effect = Exception("API Error")

        candidates = fetch_supervisor_candidates(mock_github, "owner/repo")
        assert candidates == []

    def test_queries_100_issues_not_50(self):
        """Test that fetch_supervisor_candidates queries 100 issues (Issue #803).

        Previously queried only 50 issues, causing dry-run to miss candidates.
        """
        from unittest.mock import MagicMock

        mock_github = MagicMock()
        mock_github.list_issues.return_value = []

        fetch_supervisor_candidates(mock_github, "owner/repo")

        # Verify limit parameter is 100 (not 50)
        mock_github.list_issues.assert_called_once()
        call_args = mock_github.list_issues.call_args
        assert call_args.kwargs.get("limit") == 100


class TestRenderGovernancePromptPreview:
    """Tests for governance prompt rendering."""

    def test_returns_rendered_text(self):
        """Test that rendered text is returned."""
        from unittest.mock import MagicMock, patch

        mock_config = MagicMock()

        with patch("vibe3.roles.governance.render_governance_prompt") as mock_render:
            mock_result = MagicMock()
            mock_result.rendered_text = "# Test Prompt"
            mock_render.return_value = mock_result

            result = render_governance_prompt_preview(
                config=mock_config,
                tick_count=0,
                material_override="test-material",
            )

            assert result == "# Test Prompt"
