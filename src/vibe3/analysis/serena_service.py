"""Serena service for symbol-level code analysis."""

from __future__ import annotations

import functools
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

from loguru import logger

from vibe3.analysis.serena_file_analyzer import analyze_files
from vibe3.clients import GitClient, SerenaClient
from vibe3.exceptions import SerenaError
from vibe3.models import ChangeSource

if TYPE_CHECKING:
    from vibe3.models import DeadCodeReport


@functools.lru_cache(maxsize=None)
def _is_cli_file(file_path: str) -> bool:
    """Check if file is a CLI module with Typer commands."""
    try:
        with open(file_path, "r") as f:
            content = f.read()
            return "import typer" in content or "from typer" in content
    except Exception:
        return False


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
        self._file_cache: dict[str, tuple[float, dict]] = {}
        logger.bind(domain="serena", action="init").debug("Serena service initialized")

    def analyze_symbol(self, name_path: str, relative_file: str) -> dict:
        """Analyze a specific symbol's references.

        Args:
            name_path: Symbol name (e.g., "build_module_graph")
            relative_file: Relative file path where the symbol is defined

        Returns:
            Symbol analysis with detailed reference locations
        """
        logger.bind(
            domain="serena",
            action="analyze_symbol",
            symbol=name_path,
            file=relative_file,
        ).info("Analyzing symbol")
        try:
            refs = self.client.find_references(name_path, relative_file)
            # Extract detailed reference information
            ref_list: list[dict[str, str | int]] = []
            if isinstance(refs, list):
                for ref in refs:
                    if isinstance(ref, dict):
                        ref_list.append(
                            {
                                "file": ref.get("relative_path", ""),
                                "line": ref.get("body_location", {}).get(
                                    "start_line", 0
                                ),
                                "kind": ref.get("kind", ""),
                                "context": ref.get("content_around_reference", ""),
                            }
                        )
            ref_count = len(ref_list)
            # Determine symbol type
            is_cli_command = ref_count == 0 and _is_cli_file(relative_file)
            symbol_type = "cli_command" if is_cli_command else "function"
            logger.bind(
                symbol=name_path, ref_count=ref_count, symbol_type=symbol_type
            ).success("Symbol analyzed")
            return {
                "symbol": name_path,
                "defined_in": relative_file,
                "type": symbol_type,
                "reference_count": ref_count,
                "references": ref_list,
            }
        except SerenaError:
            raise
        except Exception as e:
            raise SerenaError(f"analyze_symbol({name_path})", str(e)) from e

    def get_changed_functions(
        self, file_path: str, source: ChangeSource | None = None
    ) -> list[str]:
        """Get functions that were changed in a diff.

        Simple heuristic: find functions whose line ranges overlap with diff hunks.
        Not 100% accurate, but good enough for impact analysis.

        Args:
            file_path: Relative file path
            source: Change source (commit/branch/pr). If None, returns empty.

        Returns:
            List of function names that appear to be changed
        """
        import ast

        logger.bind(
            domain="serena",
            action="get_changed_functions",
            file=file_path,
            source_type=source.type if source else None,
        ).debug("Extracting changed functions from diff")
        try:
            # 1. Get diff hunk ranges from git_client
            if source is None:
                return []
            ranges = self.git_client.get_diff_hunk_ranges(file_path, source)
            if not ranges:
                return []
            # 2. Parse AST to find functions in these ranges
            source_code = Path(file_path).read_text(encoding="utf-8")
            tree = ast.parse(source_code)
            changed_functions: list[str] = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    func_start = node.lineno
                    func_end = getattr(node, "end_lineno", node.lineno)
                    # Check if function overlaps with any changed range
                    for range_start, range_end in ranges:
                        # Overlap: not (end < start or start > end)
                        if not (func_end < range_start or func_start > range_end):
                            changed_functions.append(node.name)
                            break
            logger.bind(file=file_path, changed_functions=changed_functions).debug(
                "Found changed functions in diff"
            )
            return changed_functions
        except Exception as e:
            logger.bind(file=file_path, error=str(e)).warning(
                "Failed to extract changed functions, falling back to full file"
            )
            return []

    def analyze_file(self, relative_file: str) -> dict:
        """Analyze symbols in a file.

        Args:
            relative_file: Relative file path

        Returns:
            File analysis dict with symbols and references
        """
        from vibe3.analysis.serena_file_analyzer import analyze_file as _analyze_file

        # Check mtime cache
        try:
            file_path = Path(relative_file)
            if file_path.exists():
                mtime = file_path.stat().st_mtime
                cached = self._file_cache.get(relative_file)
                if cached and cached[0] == mtime:
                    logger.bind(
                        domain="serena",
                        action="analyze_file",
                        file=relative_file,
                    ).debug("Using cached file analysis")
                    return cached[1]
        except Exception:
            # If mtime check fails, continue with analysis
            pass

        result = _analyze_file(relative_file, self.client, _is_cli_file)

        # Cache the result
        try:
            file_path = Path(relative_file)
            if file_path.exists():
                mtime = file_path.stat().st_mtime
                self._file_cache[relative_file] = (mtime, result)
        except Exception:
            # If caching fails, just return result
            pass

        return result

    def analyze_files(self, files: list[str]) -> dict:
        """Analyze multiple files.

        Args:
            files: List of relative file paths

        Returns:
            Analysis report dict

        Raises:
            SerenaError: If any file analysis fails
        """
        return analyze_files(files, self.client, _is_cli_file)

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
            python_files = self.git_client.get_changed_files(source, pathspec="*.py")

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

    def scan_dead_code(self, root: str | None = None) -> "DeadCodeReport":
        """Scan for dead code (unused functions) in the codebase.

        Args:
            root: Root directory to scan (None uses configured source root)

        Returns:
            DeadCodeReport with findings

        Raises:
            SerenaError: If scan fails
        """
        if root is None:
            from vibe3.config import get_source_root

            root = get_source_root()

        from vibe3.analysis.dead_code_rules import (
            get_router_functions,
            is_dead_code,
        )
        from vibe3.models import DeadCodeFinding, DeadCodeReport

        log = logger.bind(domain="serena", action="scan_dead_code", root=root)
        log.debug("Scanning for dead code")

        try:
            # Find all Python files
            root_path = Path(root)
            if not root_path.exists():
                raise SerenaError("scan_dead_code", f"Root directory not found: {root}")

            python_files = sorted(root_path.glob("**/*.py"))

            log.bind(file_count=len(python_files)).debug("Found Python files")

            # Scan each file
            findings: list[DeadCodeFinding] = []
            excluded: list[str] = []
            total_symbols = 0
            total_dead = 0
            total_excluded = 0

            for file_path in python_files:
                relative_file = str(file_path)

                try:
                    # Analyze file symbols
                    file_result = self.analyze_file(relative_file)
                    symbols = file_result.get("symbols", [])
                    total_symbols += len(symbols)

                    # Get router-decorated functions for this file (single parse)
                    router_funcs = get_router_functions(relative_file)

                    # Check each symbol
                    for sym in symbols:
                        sym_name = sym.get("name", "")
                        ref_count = sym.get("references", 0)
                        sym_type = sym.get("type", "function")

                        # Determine if CLI command
                        is_cli_command = sym_type == "cli_command"

                        # Apply dead code rules
                        is_dead, reason, confidence = is_dead_code(
                            sym_name, ref_count, is_cli_command, router_funcs
                        )

                        if is_dead:
                            # Get line number and LOC
                            start = sym.get("start_line", 0)
                            end = sym.get("end_line", 0)
                            line = start
                            loc = (
                                max(end - start + 1, 0)
                                if start > 0 and end >= start
                                else 0
                            )

                            # Type narrowing: is_dead=True → confidence != "excluded"
                            confidence_narrowed = cast(
                                Literal["high", "medium", "low"], confidence
                            )
                            findings.append(
                                DeadCodeFinding(
                                    symbol=sym_name,
                                    file=relative_file,
                                    line=line,
                                    loc=loc,
                                    confidence=confidence_narrowed,
                                    category="unused_function",
                                    reason=reason,
                                )
                            )
                            total_dead += 1
                        elif confidence == "excluded":
                            excluded.append(f"{relative_file}:{sym_name}")
                            total_excluded += 1

                except SerenaError as e:
                    log.bind(file=relative_file, error=str(e)).warning(
                        "Failed to analyze file, skipping"
                    )
                    continue

            report = DeadCodeReport(
                total_symbols=total_symbols,
                dead_code_count=total_dead,
                findings=findings,
                excluded=excluded,
                excluded_count=total_excluded,
            )

            log.bind(
                total_symbols=total_symbols,
                dead_code_count=total_dead,
                excluded_count=total_excluded,
            ).debug("Dead code scan complete")

            return report

        except SerenaError:
            raise
        except Exception as e:
            log.bind(error=str(e)).error("Dead code scan failed")
            raise SerenaError("scan_dead_code", str(e)) from e
