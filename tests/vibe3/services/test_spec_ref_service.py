"""Tests for SpecRefService."""

from pathlib import Path
from unittest.mock import patch

import pytest

from vibe3.services.spec_ref_service import SpecRefInfo, SpecRefService


class TestSpecRefService:
    """Tests for spec reference parsing."""

    @pytest.fixture
    def svc(self) -> SpecRefService:
        return SpecRefService()

    def test_parse_spec_ref_plain_number(self, svc: SpecRefService) -> None:
        """Plain number should be parsed as issue."""
        with patch.object(
            svc,
            "_fetch_issue_data",
            return_value={"number": 123, "title": "Test", "body": "Body"},
        ):
            info = svc.parse_spec_ref("123")

        assert info.kind == "issue"
        assert info.issue_number == 123
        assert info.issue_title == "Test"

    def test_parse_spec_ref_hash_number(self, svc: SpecRefService) -> None:
        """#123 format should be parsed as issue."""
        with patch.object(
            svc,
            "_fetch_issue_data",
            return_value={"number": 123, "title": "Test", "body": "Body"},
        ):
            info = svc.parse_spec_ref("#123")

        assert info.kind == "issue"
        assert info.issue_number == 123

    def test_parse_spec_ref_issue_url(self, svc: SpecRefService) -> None:
        """GitHub issue URL should be parsed as issue."""
        with patch.object(
            svc,
            "_fetch_issue_data",
            return_value={"number": 123, "title": "Test", "body": "Body"},
        ):
            info = svc.parse_spec_ref("https://github.com/owner/repo/issues/123")

        assert info.kind == "issue"
        assert info.issue_number == 123

    def test_parse_spec_ref_file_path(self, svc: SpecRefService) -> None:
        """File path should be parsed as file spec."""
        info = svc.parse_spec_ref("docs/spec.md")

        assert info.kind == "file"
        assert info.file_path == "docs/spec.md"
        assert info.display == "docs/spec.md"

    def test_issue_display_format(self, svc: SpecRefService) -> None:
        """Issue display should be #id:title format."""
        with patch.object(
            svc,
            "_fetch_issue_data",
            return_value={"number": 219, "title": "Feature X", "body": ""},
        ):
            info = svc.parse_spec_ref("219")

        assert info.display == "#219:Feature X"

    def test_issue_display_no_title(self, svc: SpecRefService) -> None:
        """Issue without title should show just #id."""
        with patch.object(
            svc,
            "_fetch_issue_data",
            return_value={"number": 123, "title": "", "body": ""},
        ):
            info = svc.parse_spec_ref("123")

        assert info.display == "#123"

    def test_fetch_issue_failure(self, svc: SpecRefService) -> None:
        """Fetch failure should still return issue kind with number."""
        with patch.object(svc, "_fetch_issue_data", return_value=None):
            info = svc.parse_spec_ref("123")

        assert info.kind == "issue"
        assert info.issue_number == 123
        assert info.issue_title is None
        assert info.display == "#123"

    def test_get_spec_content_for_issue(self, svc: SpecRefService) -> None:
        """Issue spec content should include title and body."""
        info = SpecRefInfo(
            raw="123",
            kind="issue",
            issue_number=123,
            issue_title="Test Title",
            issue_body="Test body content",
            display="#123:Test Title",
        )

        content = svc.get_spec_content_for_prompt(info)
        assert content is not None
        assert "Issue: #123" in content
        assert "Title: Test Title" in content
        assert "Test body content" in content

    def test_get_spec_content_for_file(
        self, svc: SpecRefService, tmp_path: Path
    ) -> None:
        """File spec content should read file contents."""
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("# Spec\nContent here")

        info = SpecRefInfo(
            raw=str(spec_file),
            kind="file",
            file_path=str(spec_file),
            display=str(spec_file),
        )

        content = svc.get_spec_content_for_prompt(info)
        assert content is not None
        assert "# Spec" in content
        assert "Content here" in content

    def test_get_spec_content_missing_file(self, svc: SpecRefService) -> None:
        """Missing file should return None."""
        info = SpecRefInfo(
            raw="nonexistent.md",
            kind="file",
            file_path="nonexistent.md",
            display="nonexistent.md",
        )

        content = svc.get_spec_content_for_prompt(info)
        assert content is None
