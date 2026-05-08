"""Unit tests for LocService."""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.services.loc_service import LocService


class TestLocService:
    """Test LocService."""

    def test_get_pr_loc_stats_filters_core_paths(self) -> None:
        """Test that only src/vibe3/ files are counted."""
        service = LocService()

        # Mock numstat output with files in and out of core paths
        numstat_output = """10\t5\tsrc/vibe3/services/test.py
3\t2\ttests/vibe3/services/test_test.py
7\t4\tscripts/test.sh
8\t3\tsrc/vibe3/core/main.py"""

        with patch.object(service, "_get_numstat", return_value=numstat_output):
            stats = service.get_pr_loc_stats(123)

        # Should only count src/vibe3/ files, excluding tests
        assert stats.added == 18  # 10 + 8
        assert stats.deleted == 8  # 5 + 3
        assert stats.total == 26
        assert stats.files_count == 2  # Only 2 core code files

    def test_uses_configured_code_paths_by_default(self) -> None:
        """Test that default LOC scope comes from VibeConfig."""
        config = MagicMock()
        config.code_limits.code_paths.v3_python = ["custom/core/"]

        with patch(
            "vibe3.services.loc_service.VibeConfig.get_defaults", return_value=config
        ):
            service = LocService()

        numstat_output = """4\t1\tcustom/core/service.py
10\t0\tsrc/vibe3/ignored.py"""

        with patch.object(service, "_get_numstat", return_value=numstat_output):
            stats = service.get_pr_loc_stats(123)

        assert stats.added == 4
        assert stats.deleted == 1
        assert stats.files_count == 1
        assert stats.scope == "custom/core/"

    def test_get_pr_loc_stats_aggregates_correctly(self) -> None:
        """Test that added/deleted totals are correct."""
        service = LocService()

        numstat_output = """100\t50\tsrc/vibe3/services/big_file.py
10\t5\tsrc/vibe3/core/small_file.py"""

        with patch.object(service, "_get_numstat", return_value=numstat_output):
            stats = service.get_pr_loc_stats(456)

        assert stats.added == 110
        assert stats.deleted == 55
        assert stats.total == 165
        assert stats.files_count == 2

    def test_get_pr_loc_stats_excludes_tests(self) -> None:
        """Test that test files are excluded from count."""
        service = LocService()

        # All files are in src/vibe3/ but some are tests
        numstat_output = """10\t5\tsrc/vibe3/services/real_service.py
20\t10\ttests/vibe3/services/test_real_service.py
5\t3\ttest/unit/test_helper.py"""

        with patch.object(service, "_get_numstat", return_value=numstat_output):
            stats = service.get_pr_loc_stats(789)

        # Should only count the non-test file
        assert stats.added == 10
        assert stats.deleted == 5
        assert stats.files_count == 1

    def test_get_branch_loc_stats(self) -> None:
        """Test that branch diff works."""
        service = LocService()
        service.git_client = MagicMock()
        service.git_client.get_numstat.return_value = "15\t8\tsrc/vibe3/new_file.py"

        stats = service.get_branch_loc_stats("feature-branch", "main")

        assert stats.added == 15
        assert stats.deleted == 8
        assert stats.total == 23
        assert stats.files_count == 1

    def test_handles_binary_files(self) -> None:
        """Test that binary files (shown as - in numstat) are handled."""
        service = LocService()

        # Binary files show as "-" in numstat
        numstat_output = """-\t-\tsrc/vibe3/assets/image.png
10\t5\tsrc/vibe3/code/real.py"""

        with patch.object(service, "_get_numstat", return_value=numstat_output):
            stats = service.get_pr_loc_stats(100)

        # Should skip binary file, count only real.py
        assert stats.added == 10
        assert stats.deleted == 5
        assert stats.files_count == 1

    def test_handles_malformed_lines(self) -> None:
        """Test that malformed numstat lines are skipped gracefully."""
        service = LocService()

        # Mix of valid and malformed lines
        numstat_output = """10\t5\tsrc/vibe3/good.py
invalid line here
8\t3\t
\t\tbroken
7\t2\tsrc/vibe3/another.py"""

        with patch.object(service, "_get_numstat", return_value=numstat_output):
            stats = service.get_pr_loc_stats(200)

        # Should count only valid lines
        assert stats.added == 17  # 10 + 7
        assert stats.deleted == 7  # 5 + 2
        assert stats.files_count == 2

    def test_raises_when_numstat_cannot_be_loaded(self) -> None:
        """Test that diff loading failures are surfaced to the caller."""
        service = LocService()

        with patch.object(service, "_get_numstat", side_effect=Exception("Git error")):
            with pytest.raises(Exception, match="Git error"):
                service.get_pr_loc_stats(300)

    def test_get_numstat_delegates_to_git_client(self) -> None:
        """Test that _get_numstat uses public GitClient.get_numstat()."""
        from vibe3.models.change_source import PRSource

        service = LocService()
        service.git_client = MagicMock()
        service.git_client.get_numstat.return_value = "10\t5\tsrc/vibe3/test.py"

        result = service._get_numstat(PRSource(pr_number=1))

        service.git_client.get_numstat.assert_called_once()
        assert result == "10\t5\tsrc/vibe3/test.py"
