"""Tests for snapshot diff facade."""

from unittest.mock import MagicMock, patch

from vibe3.models import DiffSummary, StructureSnapshot


class TestGetDiffSummary:
    """Tests for get_diff_summary fallback chain."""

    def test_level1_full_snapshot_diff_when_baseline_exists(self) -> None:
        """When baseline exists, should compute full snapshot diff."""
        from vibe3.analysis.snapshot_diff_facade import get_diff_summary

        mock_baseline = MagicMock(spec=StructureSnapshot)
        mock_baseline.snapshot_id = "baseline-123"

        mock_current = MagicMock(spec=StructureSnapshot)
        mock_current.snapshot_id = "current-456"

        mock_diff_summary = DiffSummary(
            files_added=2,
            files_removed=1,
            files_modified=3,
            total_loc_delta=150,
        )
        mock_diff_result = MagicMock()
        mock_diff_result.summary = mock_diff_summary

        with patch(
            "vibe3.analysis.snapshot_diff_facade.load_branch_baseline",
            return_value=mock_baseline,
        ):
            with patch(
                "vibe3.analysis.snapshot_diff_facade.build_snapshot",
                return_value=mock_current,
            ):
                with patch(
                    "vibe3.analysis.snapshot_diff.compute_diff",
                    return_value=mock_diff_result,
                ):
                    result = get_diff_summary("feature-branch", "main")

        assert result.files_added == 2
        assert result.files_removed == 1
        assert result.files_modified == 3
        assert result.total_loc_delta == 150

    def test_level2_git_diff_when_no_baseline(self) -> None:
        """When no baseline exists, should fall back to git numstat + name-status."""
        from vibe3.analysis.snapshot_diff_facade import get_diff_summary

        with patch(
            "vibe3.analysis.snapshot_diff_facade.load_branch_baseline",
            return_value=None,
        ):
            mock_git = MagicMock()
            mock_git.get_numstat.return_value = (
                "10\t5\tnew_file.py\n20\t10\tmodified_file.py\n-\t-\tbinary.png"
            )
            mock_git.get_name_status.return_value = (
                "A\tnew_file.py\nM\tmodified_file.py\nM\tbinary.png"
            )

            with patch(
                "vibe3.analysis.snapshot_diff_facade.GitClient",
                return_value=mock_git,
            ):
                result = get_diff_summary("feature-branch", "main")

        assert result.files_added == 1  # new_file.py
        assert result.files_modified == 2  # modified_file.py + binary.png
        assert result.files_removed == 0
        # LOC delta doubles because both committed and uncommitted sources
        # return the same mock data: (10-5)+(20-10)+(0-0) = 15 × 2 = 30
        assert result.total_loc_delta == 30

    def test_level3_empty_summary_when_git_fails(self) -> None:
        """When git fails, should return empty DiffSummary."""
        from vibe3.analysis.snapshot_diff_facade import get_diff_summary

        with patch(
            "vibe3.analysis.snapshot_diff_facade.load_branch_baseline",
            return_value=None,
        ):
            with patch(
                "vibe3.analysis.snapshot_diff_facade.GitClient",
                side_effect=Exception("Git error"),
            ):
                result = get_diff_summary("feature-branch", "main")

        assert result == DiffSummary()


class TestDiffViaGit:
    """Tests for _diff_via_git numstat + name-status parsing."""

    def test_classifies_files_by_name_status(self) -> None:
        """Should classify files as A/M/D based on name-status output."""
        from vibe3.analysis.snapshot_diff_facade import _diff_via_git

        mock_git = MagicMock()
        mock_git.get_numstat.return_value = (
            "10\t5\tfile1.py\n20\t0\tfile2.py\n0\t10\tfile3.py"
        )
        mock_git.get_name_status.return_value = "A\tfile1.py\nM\tfile2.py\nD\tfile3.py"

        result = _diff_via_git(mock_git, "feature-branch", "main")

        assert result.files_added == 1  # file1.py
        assert result.files_modified == 1  # file2.py
        assert result.files_removed == 1  # file3.py

    def test_handles_rename_status(self) -> None:
        """Rename (R) should count as both added and removed."""
        from vibe3.analysis.snapshot_diff_facade import _diff_via_git

        mock_git = MagicMock()
        mock_git.get_numstat.return_value = "0\t0\told.py\tnew.py"
        mock_git.get_name_status.return_value = "R100\told.py\tnew.py"

        result = _diff_via_git(mock_git, "feature-branch", "main")

        assert result.files_added == 1
        assert result.files_removed == 1
        assert result.files_modified == 0

    def test_handles_copy_status(self) -> None:
        """Copy (C) should count as added only."""
        from vibe3.analysis.snapshot_diff_facade import _diff_via_git

        mock_git = MagicMock()
        mock_git.get_numstat.return_value = "10\t0\tnew.py"
        mock_git.get_name_status.return_value = "C100\told.py\tnew.py"

        result = _diff_via_git(mock_git, "feature-branch", "main")

        assert result.files_added == 1
        assert result.files_removed == 0
        assert result.files_modified == 0

    def test_falls_back_to_all_modified_when_name_status_fails(self) -> None:
        """Should fall back to all-modified when get_name_status fails."""
        from vibe3.analysis.snapshot_diff_facade import _diff_via_git

        mock_git = MagicMock()
        mock_git.get_numstat.return_value = (
            "10\t5\tfile1.py\n20\t0\tfile2.py\n0\t10\tfile3.py"
        )
        mock_git.get_name_status.side_effect = Exception("Git error")

        result = _diff_via_git(mock_git, "feature-branch", "main")

        # Fallback: all files counted as modified
        assert result.files_added == 0
        assert result.files_removed == 0
        assert result.files_modified == 3

    def test_computes_loc_delta(self) -> None:
        """Should compute total LOC delta from numstat (combined sources)."""
        from vibe3.analysis.snapshot_diff_facade import _diff_via_git

        mock_git = MagicMock()
        mock_git.get_numstat.return_value = (
            "10\t5\tfile1.py\n20\t-\tfile2.py\n-\t10\tfile3.py"
        )
        mock_git.get_name_status.return_value = "M\tfile1.py\nA\tfile2.py\nD\tfile3.py"

        result = _diff_via_git(mock_git, "feature-branch", "main")

        # LOC delta doubles because both committed and uncommitted sources
        # return the same mock data: 10-5 + 20-0 + 0-10 = 15 × 2 = 30
        assert result.total_loc_delta == 30

    def test_handles_binary_files(self) -> None:
        """Binary files (- in numstat) should not affect LOC delta."""
        from vibe3.analysis.snapshot_diff_facade import _diff_via_git

        mock_git = MagicMock()
        mock_git.get_numstat.return_value = "-\t-\tbinary.png"
        mock_git.get_name_status.return_value = "A\tbinary.png"

        result = _diff_via_git(mock_git, "feature-branch", "main")

        assert result.total_loc_delta == 0
        assert result.files_added == 1

    def test_handles_empty_output(self) -> None:
        """Empty output should return zero counts."""
        from vibe3.analysis.snapshot_diff_facade import _diff_via_git

        mock_git = MagicMock()
        mock_git.get_numstat.return_value = ""
        mock_git.get_name_status.return_value = ""

        result = _diff_via_git(mock_git, "feature-branch", "main")

        assert result.total_loc_delta == 0
        assert result.files_added == 0
        assert result.files_removed == 0
        assert result.files_modified == 0

    def test_numstat_failure_returns_empty_summary(self) -> None:
        """When get_numstat fails, should return empty DiffSummary."""
        from vibe3.analysis.snapshot_diff_facade import _diff_via_git

        mock_git = MagicMock()
        mock_git.get_numstat.side_effect = Exception("Git error")
        mock_git.get_name_status.return_value = ""

        result = _diff_via_git(mock_git, "feature-branch", "main")

        assert result == DiffSummary()

    def test_double_failure_returns_empty_summary(self) -> None:
        """When both git ops fail, should return empty DiffSummary."""
        from vibe3.analysis.snapshot_diff_facade import _diff_via_git

        mock_git = MagicMock()
        mock_git.get_numstat.side_effect = Exception("Numstat error")
        mock_git.get_name_status.side_effect = Exception("Name-status error")

        result = _diff_via_git(mock_git, "feature-branch", "main")

        # Should return empty summary without UnboundLocalError
        assert result.files_added == 0
        assert result.files_removed == 0
        assert result.files_modified == 0
        assert result.total_loc_delta == 0
