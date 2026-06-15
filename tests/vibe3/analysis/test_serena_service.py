"""SerenaService 单元测试."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.analysis.serena_service import SerenaService, _is_cli_file
from vibe3.exceptions import SerenaError
from vibe3.models.change_source import BranchSource, CommitSource, UncommittedSource


@pytest.fixture(autouse=True)
def _clear_cli_file_cache() -> None:
    """Clear _is_cli_file cache before and after each test."""
    _is_cli_file.cache_clear()
    yield
    _is_cli_file.cache_clear()


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
        # Default behavior: return all files when called without pathspec
        # Return only Python files when called with pathspec="*.py"
        git.get_changed_files.side_effect = lambda source, pathspec=None: (
            ["src/vibe3/config/loader.py", "bin/vibe"]
            if pathspec is None
            else ["src/vibe3/config/loader.py"]
        )
        return git

    def test_changed_files_in_report(
        self, mock_client: MagicMock, mock_git: MagicMock
    ) -> None:
        service = SerenaService(client=mock_client, git_client=mock_git)
        source = UncommittedSource()
        result = service.analyze_changes(source)
        assert "changed_files" in result
        assert result["changed_files"] == ["src/vibe3/config/loader.py", "bin/vibe"]

    def test_only_python_files_analyzed(
        self, mock_client: MagicMock, mock_git: MagicMock
    ) -> None:
        service = SerenaService(client=mock_client, git_client=mock_git)
        source = UncommittedSource()
        result = service.analyze_changes(source)

        # get_symbols_overview 只应被调用一次（只有 loader.py 是 Python）
        assert mock_client.get_symbols_overview.call_count == 1

        # 验证结果中只包含 Python 文件
        analyzed_files = [f["file"] for f in result["files"]]  # type: ignore[index]
        assert analyzed_files == ["src/vibe3/config/loader.py"]
        assert "bin/vibe" not in analyzed_files

        # 验证 changed_files 包含原始所有文件
        assert result["changed_files"] == ["src/vibe3/config/loader.py", "bin/vibe"]

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
        from vibe3.clients.git_client import GitClient

        git_client = GitClient()
        git_client.get_untracked_files = lambda: [str(new_file)]

        # Mock SerenaClient to provide symbols overview
        client = MagicMock()
        client.get_symbols_overview.return_value = {
            "Function": [
                {
                    "kind": 12,
                    "name_path": "alpha",
                    "body_location": {"start_line": 1, "end_line": 2},
                },
                {
                    "kind": 12,
                    "name_path": "beta",
                    "body_location": {"start_line": 4, "end_line": 5},
                },
            ]
        }
        service = SerenaService(client=client, git_client=git_client)

        result = service.get_changed_functions(
            str(new_file), source=UncommittedSource()
        )

        assert result == ["alpha", "beta"]


class TestAnalyzeSymbol:
    """analyze_symbol 测试."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        return MagicMock()

    def test_normal_reference_extraction(self, mock_client: MagicMock) -> None:
        """测试正常提取引用。"""
        mock_client.find_references.return_value = [
            {
                "relative_path": "src/caller.py",
                "body_location": {"start_line": 10},
                "kind": "call",
                "content_around_reference": "foo()",
            }
        ]
        service = SerenaService(client=mock_client)
        result = service.analyze_symbol("foo", "src/def.py")

        assert result["symbol"] == "foo"
        assert result["type"] == "function"
        assert result["reference_count"] == 1
        assert result["references"][0]["file"] == "src/caller.py"
        assert result["references"][0]["line"] == 10

    def test_empty_result_handling(self, mock_client: MagicMock) -> None:
        """测试无引用情况。"""
        mock_client.find_references.return_value = []
        service = SerenaService(client=mock_client)

        with patch("vibe3.analysis.serena_service._is_cli_file", return_value=False):
            result = service.analyze_symbol("foo", "src/def.py")

        assert result["reference_count"] == 0
        assert result["type"] == "function"
        assert result["references"] == []

    def test_serena_error_handling(self, mock_client: MagicMock) -> None:
        """测试 SerenaError 异常处理。"""
        mock_client.find_references.side_effect = SerenaError(
            "find_references", "timeout"
        )
        service = SerenaService(client=mock_client)

        with pytest.raises(SerenaError) as excinfo:
            service.analyze_symbol("foo", "src/def.py")
        assert "timeout" in str(excinfo.value)

    def test_generic_exception_wrapped(self, mock_client: MagicMock) -> None:
        """测试普通异常被包装为 SerenaError。"""
        mock_client.find_references.side_effect = ValueError("unexpected")
        service = SerenaService(client=mock_client)

        with pytest.raises(SerenaError) as excinfo:
            service.analyze_symbol("foo", "src/def.py")
        assert "analyze_symbol(foo)" in str(excinfo.value)
        assert "unexpected" in str(excinfo.value)

    def test_cli_command_detection(self, mock_client: MagicMock) -> None:
        """测试 CLI 命令检测逻辑。"""
        mock_client.find_references.return_value = []
        service = SerenaService(client=mock_client)

        with patch("vibe3.analysis.serena_service._is_cli_file", return_value=True):
            result = service.analyze_symbol("main", "bin/vibe")

        assert result["reference_count"] == 0
        assert result["type"] == "cli_command"


class TestIsCliFile:
    """_is_cli_file caching tests."""

    def test_caches_result(self, tmp_path: Path) -> None:
        """Repeated calls with same path should use cache."""
        cli_file = tmp_path / "cli.py"
        cli_file.write_text("import typer\napp = typer.Typer()\n")

        with patch("builtins.open", side_effect=open) as mock_open:
            result1 = _is_cli_file(str(cli_file))
            result2 = _is_cli_file(str(cli_file))

            assert result1 is True
            assert result2 is True
            assert mock_open.call_count == 1

    def test_non_cli_file_cached(self, tmp_path: Path) -> None:
        """Non-CLI files should also be cached."""
        normal_file = tmp_path / "normal.py"
        normal_file.write_text("def foo(): pass\n")

        with patch("builtins.open", side_effect=open) as mock_open:
            result1 = _is_cli_file(str(normal_file))
            result2 = _is_cli_file(str(normal_file))

            assert result1 is False
            assert result2 is False
            assert mock_open.call_count == 1

    def test_nonexistent_file_returns_false(self) -> None:
        """Missing files should return False (not cached on error)."""
        result = _is_cli_file("/nonexistent/path.py")
        assert result is False


class TestScanDeadCode:
    """scan_dead_code tests."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        client = MagicMock()
        # Return overview with body_location
        client.get_symbols_overview.return_value = {
            "kind": 12,
            "name_path": "unused_func",
            "body_location": {"start_line": 10, "end_line": 25},
        }
        # Return empty references (dead code)
        client.find_references.return_value = []
        return client

    def test_line_and_loc_populated_from_body_location(
        self, mock_client: MagicMock
    ) -> None:
        """Test that line and loc are populated from body_location."""
        # Mock Path.glob to return only one test file
        with patch("vibe3.analysis.serena_service.Path") as mock_path:
            mock_root = MagicMock()
            mock_root.exists.return_value = True
            mock_file = MagicMock()
            mock_file.__str__ = lambda self: "src/vibe3/test.py"
            mock_root.glob.return_value = [mock_file]
            mock_path.return_value = mock_root

            service = SerenaService(client=mock_client)
            report = service.scan_dead_code()

            # Should have one finding
            assert len(report.findings) == 1
            finding = report.findings[0]

            # line should be start_line
            assert finding.line == 10
            # loc should be end_line - start_line + 1 = 25 - 10 + 1 = 16
            assert finding.loc == 16

    def test_line_and_loc_fallback_to_zero(self) -> None:
        """Test that line and loc fallback to 0 when body_location is missing."""
        client = MagicMock()
        # Return overview without body_location (simple string list)
        client.get_symbols_overview.return_value = {"Function": ["unused_func"]}
        # Return empty references (dead code)
        client.find_references.return_value = []

        # Mock Path.glob to return only one test file
        with patch("vibe3.analysis.serena_service.Path") as mock_path:
            mock_root = MagicMock()
            mock_root.exists.return_value = True
            mock_file = MagicMock()
            mock_file.__str__ = lambda self: "src/vibe3/test.py"
            mock_root.glob.return_value = [mock_file]
            mock_path.return_value = mock_root

            service = SerenaService(client=client)
            report = service.scan_dead_code()

            # Should have one finding
            assert len(report.findings) == 1
            finding = report.findings[0]

            # line and loc should be 0 (fallback)
            assert finding.line == 0
            assert finding.loc == 0

    def test_loc_calculation_edge_cases(self) -> None:
        """Test LOC calculation with edge cases."""
        client = MagicMock()
        # Test case: start_line = 5, end_line = 5 (single line function)
        client.get_symbols_overview.return_value = {
            "kind": 12,
            "name_path": "single_line_func",
            "body_location": {"start_line": 5, "end_line": 5},
        }
        client.find_references.return_value = []

        # Mock Path.glob to return only one test file
        with patch("vibe3.analysis.serena_service.Path") as mock_path:
            mock_root = MagicMock()
            mock_root.exists.return_value = True
            mock_file = MagicMock()
            mock_file.__str__ = lambda self: "src/vibe3/test.py"
            mock_root.glob.return_value = [mock_file]
            mock_path.return_value = mock_root

            service = SerenaService(client=client)
            report = service.scan_dead_code()

            assert len(report.findings) == 1
            finding = report.findings[0]
            assert finding.line == 5
            # loc should be 5 - 5 + 1 = 1
            assert finding.loc == 1

    def test_loc_zero_when_invalid_range(self) -> None:
        """Test that loc is 0 when start_line > end_line (invalid range)."""
        client = MagicMock()
        # Invalid range: start_line > end_line
        client.get_symbols_overview.return_value = {
            "kind": 12,
            "name_path": "invalid_func",
            "body_location": {"start_line": 20, "end_line": 10},
        }
        client.find_references.return_value = []

        # Mock Path.glob to return only one test file
        with patch("vibe3.analysis.serena_service.Path") as mock_path:
            mock_root = MagicMock()
            mock_root.exists.return_value = True
            mock_file = MagicMock()
            mock_file.__str__ = lambda self: "src/vibe3/test.py"
            mock_root.glob.return_value = [mock_file]
            mock_path.return_value = mock_root

            service = SerenaService(client=client)
            report = service.scan_dead_code()

            assert len(report.findings) == 1
            finding = report.findings[0]
            assert finding.line == 20
            # loc should be 0 because start > end
            assert finding.loc == 0
