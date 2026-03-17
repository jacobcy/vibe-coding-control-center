"""Serena service for symbol-level code analysis."""

from datetime import datetime, timezone

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.clients.serena_client import (
    SerenaClient,
    count_references,
    extract_function_names,
)
from vibe3.exceptions import SerenaError
from vibe3.models.change_source import ChangeSource


class SerenaService:
    """Service for analyzing code symbols using Serena."""

    def __init__(
        self,
        client: SerenaClient | None = None,
        git_client: GitClient | None = None,
    ) -> None:
        """Initialize Serena service.

        Args:
            client: Serena client instance
            git_client: Git client instance（用于 analyze_changes）
        """
        self.client = client or SerenaClient()
        self.git_client = git_client or GitClient()
        logger.bind(domain="serena", action="init").debug("Serena service initialized")

    def analyze_file(self, relative_file: str) -> dict:
        """Analyze symbols in a file.

        Args:
            relative_file: Relative file path

        Returns:
            File analysis dict with symbols and references
        """
        logger.bind(
            domain="serena",
            action="analyze_file",
            file=relative_file,
        ).info("Analyzing file")

        try:
            overview = self.client.get_symbols_overview(relative_file)
            symbols = []

            for func_name in extract_function_names(overview):
                try:
                    refs = self.client.find_references(func_name, relative_file)
                    symbols.append(
                        {
                            "name": func_name,
                            "status": "ok",
                            "references": count_references(refs),
                        }
                    )
                except SerenaError as e:
                    symbols.append(
                        {
                            "name": func_name,
                            "status": "error",
                            "references": 0,
                            "error": str(e),
                        }
                    )

            logger.bind(
                file=relative_file,
                symbol_count=len(symbols),
            ).success("File analyzed")

            return {
                "file": relative_file,
                "status": "ok",
                "symbols": symbols,
            }

        except SerenaError as e:
            logger.bind(
                file=relative_file,
                error=str(e),
            ).error("File analysis failed")
            return {
                "file": relative_file,
                "status": "error",
                "error": str(e),
                "symbols": [],
            }

    def analyze_files(self, files: list[str]) -> dict:
        """Analyze multiple files.

        Args:
            files: List of relative file paths

        Returns:
            Analysis report dict
        """
        logger.bind(
            domain="serena",
            action="analyze_files",
            file_count=len(files),
        ).info("Analyzing files")

        report: dict[str, str | dict | list[dict]] = {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "health_check": {"status": "ok", "log": ""},
            "files": [],
        }

        for file in files:
            result = self.analyze_file(file)
            files_list = report["files"]
            assert isinstance(files_list, list)
            files_list.append(result)

        # Summary
        files_list = report["files"]
        assert isinstance(files_list, list)
        file_errors = sum(
            1 for f in files_list if isinstance(f, dict) and f.get("status") != "ok"
        )
        symbol_errors = sum(
            1
            for f in files_list
            if isinstance(f, dict)
            for s in f.get("symbols", [])
            if isinstance(s, dict) and s.get("status") != "ok"
        )
        report["summary"] = {
            "files": len(report["files"]),
            "file_errors": file_errors,
            "symbol_errors": symbol_errors,
        }

        logger.bind(
            total_files=len(files),
            file_errors=file_errors,
            symbol_errors=symbol_errors,
        ).success("Files analyzed")

        return report

    def analyze_changes(self, source: ChangeSource) -> dict[str, object]:
        """统一改动分析入口 - 支持 PR/Commit/Branch/Uncommitted.

        Args:
            source: 改动源

        Returns:
            分析报告 dict，包含 changed_files 和每个文件的符号分析
        """
        log = logger.bind(
            domain="serena", action="analyze_changes", source_type=source.type
        )
        log.info("Analyzing changes")

        try:
            files = self.git_client.get_changed_files(source)
            python_files = [f for f in files if f.endswith(".py")]

            log.bind(
                total_files=len(files),
                python_files=len(python_files),
            ).debug("Filtered Python files for analysis")

            report = (
                self.analyze_files(python_files)
                if python_files
                else {
                    "generated_at": datetime.now(timezone.utc).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    ),
                    "health_check": {"status": "ok", "log": ""},
                    "files": [],
                    "summary": {"files": 0, "file_errors": 0, "symbol_errors": 0},
                }
            )

            report["changed_files"] = files  # type: ignore[index]
            report["source_type"] = source.type  # type: ignore[index]

            log.bind(changed_files=len(files)).success("Change analysis complete")
            return report

        except Exception as e:
            log.bind(error=str(e)).error("Change analysis failed")
            raise SerenaError("analyze_changes", str(e)) from e
