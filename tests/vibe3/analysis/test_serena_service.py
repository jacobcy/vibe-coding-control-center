"""SerenaService 单元测试."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.analysis.serena_service import SerenaService
from vibe3.exceptions import SerenaError
from vibe3.models.change_source import BranchSource, CommitSource, UncommittedSource


class TestAnalyzeFile:
    """analyze_file 测试."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        client = MagicMock()
        client.get_symbols_overview.return_value = {
            "Function": ["load_config", "get_config"]
        }
        client.find_references.return_value = [{"name_path": "caller"}]
        return client

    def test_returns_ok_status(self, mock_client: MagicMock) -> None:
        service = SerenaService(client=mock_client)
        result = service.analyze_file("src/vibe3/config/loader.py")
        assert result["file"] == "src/vibe3/config/loader.py"
        assert "symbols" in result

    def test_symbols_extracted(self, mock_client: MagicMock) -> None:
        service = SerenaService(client=mock_client)
        result = service.analyze_file("src/vibe3/config/loader.py")
        assert len(result["symbols"]) > 0

    def test_returns_error_on_client_failure(self) -> None:
        client = MagicMock()
        client.get_symbols_overview.side_effect = SerenaError(
            "get_symbols_overview", "timeout"
        )
        service = SerenaService(client=client)

        # Fail-fast: 应该抛出异常，而不是返回错误字典
        with pytest.raises(SerenaError):
            service.analyze_file("src/vibe3/config/loader.py")


class TestAnalyzeFiles:
    """analyze_files 测试."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        client = MagicMock()
        client.get_symbols_overview.return_value = {"Function": ["foo"]}
        client.find_references.return_value = []
        return client

    def test_summary_counts_files(self, mock_client: MagicMock) -> None:
        service = SerenaService(client=mock_client)
        with patch("vibe3.analysis.serena_file_analyzer.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            result = service.analyze_files(["a.py", "b.py"])
        assert result["summary"]["files"] == 2  # type: ignore[index]

    def test_empty_files_list(self, mock_client: MagicMock) -> None:
        service = SerenaService(client=mock_client)
        result = service.analyze_files([])
        assert result["summary"]["files"] == 0  # type: ignore[index]


class TestAnalyzeChanges:
    """analyze_changes 统一入口测试."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        client = MagicMock()
        client.get_symbols_overview.return_value = {"Function": ["foo"]}
        client.find_references.return_value = []
        return client

    @pytest.fixture
    def mock_git(self) -> MagicMock:
        git = MagicMock()
        git.get_changed_files.return_value = ["src/vibe3/config/loader.py", "bin/vibe"]
        return git

    def test_changed_files_in_report(
        self, mock_client: MagicMock, mock_git: MagicMock
    ) -> None:
        service = SerenaService(client=mock_client, git_client=mock_git)
        source = UncommittedSource()
        result = service.analyze_changes(source)
        assert "changed_files" in result
        assert len(result["changed_files"]) == 2  # type: ignore[index]

    def test_only_python_files_analyzed(
        self, mock_client: MagicMock, mock_git: MagicMock
    ) -> None:
        service = SerenaService(client=mock_client, git_client=mock_git)
        source = UncommittedSource()
        service.analyze_changes(source)
        # get_symbols_overview 只应被调用一次（只有 loader.py 是 Python）
        assert mock_client.get_symbols_overview.call_count == 1

    def test_source_type_in_report(
        self, mock_client: MagicMock, mock_git: MagicMock
    ) -> None:
        service = SerenaService(client=mock_client, git_client=mock_git)
        source = BranchSource(branch="feature/test", base="main")
        result = service.analyze_changes(source)
        assert result["source_type"] == "branch"


class TestAnalyzeFilesSkipped:
    """analyze_files skipped files handling tests."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmp:
            # Create test files
            (Path(tmp) / "file1.py").write_text("def foo(): pass\n")
            (Path(tmp) / "file2.py").write_text("def bar(): pass\n")
            (Path(tmp) / "file3.py").write_text("def baz(): pass\n")
            yield Path(tmp)

    def test_analyze_files_all_exist(self, temp_dir):
        """Test analyzing files that all exist."""
        # Mock the client and its methods
        mock_client = MagicMock()
        mock_client.get_symbols_overview.return_value = {
            "functions": [{"name": "test_func", "start_line": 1}]
        }
        mock_client.find_references.return_value = {"references": []}

        # Create service
        service = SerenaService(client=mock_client)

        # Test with files that exist
        files = [
            str(temp_dir / "file1.py"),
            str(temp_dir / "file2.py"),
            str(temp_dir / "file3.py"),
        ]
        result = service.analyze_files(files)

        assert len(result["files"]) == 3
        assert "skipped_files" in result
        assert len(result["skipped_files"]) == 0
        assert result["summary"]["skipped_files"] == 0

    def test_analyze_files_some_missing(self, temp_dir):
        """Test analyzing files where some don't exist."""
        # Mock the client
        mock_client = MagicMock()
        mock_client.get_symbols_overview.return_value = {
            "functions": [{"name": "test_func", "start_line": 1}]
        }
        mock_client.find_references.return_value = {"references": []}

        # Create service
        service = SerenaService(client=mock_client)

        # Test with mix of existing and non-existing files
        result = service.analyze_files(
            [
                str(temp_dir / "file1.py"),  # exists
                str(temp_dir / "deleted.py"),  # doesn't exist
                str(temp_dir / "file2.py"),  # exists
            ]
        )

        assert len(result["files"]) == 2
        assert len(result["skipped_files"]) == 1
        assert str(temp_dir / "deleted.py") in result["skipped_files"]
        assert result["summary"]["skipped_files"] == 1

    def test_analyze_files_all_missing(self, temp_dir):
        """Test analyzing files where none exist."""
        # Mock the client
        mock_client = MagicMock()

        # Create service
        service = SerenaService(client=mock_client)

        # Test with all non-existing files
        result = service.analyze_files(
            [
                str(temp_dir / "deleted1.py"),
                str(temp_dir / "deleted2.py"),
            ]
        )

        assert len(result["files"]) == 0
        assert len(result["skipped_files"]) == 2
        assert result["summary"]["skipped_files"] == 2

    def test_get_changed_functions_missing_file(self, temp_dir):
        """Test get_changed_functions with missing file."""
        # Mock git client
        mock_git_client = MagicMock()

        # Create service
        service = SerenaService(git_client=mock_git_client)

        # Mock get_diff_hunk_ranges method on git_client
        mock_git_client.get_diff_hunk_ranges.return_value = [(1, 10)]
        result = service.get_changed_functions(
            str(temp_dir / "deleted.py"), source=CommitSource(sha="abc123")
        )

        # Should return empty list for missing file
        assert result == []

    def test_get_changed_functions_untracked_file(self, temp_dir):
        """Test get_changed_functions treats untracked files as full-file changes."""
        new_file = temp_dir / "new_module.py"
        new_file.write_text(
            "def alpha():\n" "    return 1\n" "\n" "def beta():\n" "    return 2\n"
        )

        # Use real GitClient but mock its get_untracked_files method
        from vibe3.clients import GitClient

        git_client = GitClient()
        git_client.get_untracked_files = lambda: [str(new_file)]

        service = SerenaService(git_client=git_client)

        result = service.get_changed_functions(
            str(new_file), source=UncommittedSource()
        )

        assert result == ["alpha", "beta"]
