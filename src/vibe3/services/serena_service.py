"""Serena service for symbol-level code analysis."""

from datetime import datetime, timezone

from loguru import logger

from vibe3.clients.serena_client import (
    SerenaClient,
    count_references,
    extract_function_names,
)
from vibe3.exceptions import SerenaError


class SerenaService:
    """Service for analyzing code symbols using Serena."""

    def __init__(self, client: SerenaClient | None = None) -> None:
        """Initialize Serena service.

        Args:
            client: Serena client instance
        """
        self.client = client or SerenaClient()
        logger.info("Serena service initialized")

    def analyze_file(self, relative_file: str) -> dict:
        """Analyze symbols in a file.

        Args:
            relative_file: Relative file path

        Returns:
            File analysis dict with symbols and references
        """
        logger.info("Analyzing file", file=relative_file)

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

            logger.info(
                "File analyzed",
                file=relative_file,
                symbol_count=len(symbols),
            )

            return {
                "file": relative_file,
                "status": "ok",
                "symbols": symbols,
            }

        except SerenaError as e:
            logger.error("File analysis failed", file=relative_file, error=str(e))
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
        logger.info("Analyzing files", file_count=len(files))

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

        logger.info(
            "Files analyzed",
            total_files=len(files),
            file_errors=file_errors,
            symbol_errors=symbol_errors,
        )

        return report
