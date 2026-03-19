"""SerenaService 单元测试."""

from unittest.mock import MagicMock

import pytest

from vibe3.exceptions import SerenaError
from vibe3.models.change_source import BranchSource, UncommittedSource
from vibe3.services.serena_service import SerenaService


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
