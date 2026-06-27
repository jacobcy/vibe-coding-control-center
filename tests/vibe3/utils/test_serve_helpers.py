"""Tests for vibe3.utils.serve_helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

from vibe3.utils.serve_helpers import extract_material_from_log


class TestExtractMaterialFromLog:
    """Tests for extract_material_from_log function."""

    def test_extracts_material_from_valid_log_path(self) -> None:
        """Should extract material slug from well-formed governance log path."""
        job = MagicMock()
        job.log_path = "/some/path/roadmap-intake-20260628-010215-t5.log"
        assert extract_material_from_log(job) == "roadmap-intake"

    def test_extracts_multi_hyphen_material(self) -> None:
        """Should extract material slug with multiple hyphens."""
        job = MagicMock()
        job.log_path = "/path/cron-supervisor-20260627-120000-t8.log"
        assert extract_material_from_log(job) == "cron-supervisor"

    def test_returns_none_when_no_log_path(self) -> None:
        """Should return None when job has no log_path attribute."""
        job = MagicMock(spec=[])  # no log_path attribute
        assert extract_material_from_log(job) is None

    def test_returns_none_when_log_path_is_none(self) -> None:
        """Should return None when log_path is None."""
        job = MagicMock()
        job.log_path = None
        assert extract_material_from_log(job) is None

    def test_returns_none_when_log_path_is_empty(self) -> None:
        """Should return None when log_path is empty string."""
        job = MagicMock()
        job.log_path = ""
        assert extract_material_from_log(job) is None

    def test_returns_none_for_non_matching_filename(self) -> None:
        """Should return None when filename does not match expected pattern."""
        job = MagicMock()
        job.log_path = "/path/random-file.txt"
        assert extract_material_from_log(job) is None

    def test_returns_none_for_non_governance_log(self) -> None:
        """Should return None for issue-based log paths."""
        job = MagicMock()
        job.log_path = "/path/issue-1234/run.log"
        assert extract_material_from_log(job) is None

    def test_handles_basename_only_path(self) -> None:
        """Should work when log_path is just a filename without directory."""
        job = MagicMock()
        job.log_path = "roadmap-intake-20260628-010215-t5.log"
        assert extract_material_from_log(job) == "roadmap-intake"
