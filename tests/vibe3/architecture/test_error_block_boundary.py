"""Architecture boundary tests: ERROR and BLOCK modules must stay decoupled."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# Anchor to project root (tests/vibe3/architecture/test_error_block_boundary.py)
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def get_file_content(file_path: Path) -> str:
    """Read file content, return empty string if not exists."""
    if not file_path.exists():
        return ""
    return file_path.read_text(encoding="utf-8")


def strip_docstrings_and_comments(content: str) -> str:
    """Remove docstrings and comments from Python source for reliable scanning."""
    # Remove triple-quoted strings (docstrings/multiline strings)
    cleaned = re.sub(r'""".*?"""', "", content, flags=re.DOTALL)
    cleaned = re.sub(r"'''.*?'''", "", cleaned, flags=re.DOTALL)
    # Remove single-line comments
    lines = []
    for line in cleaned.split("\n"):
        # Strip # comments (not inside strings since we removed those)
        if "#" in line:
            code_part = line.split("#")[0]
            lines.append(code_part)
        else:
            lines.append(line)
    return "\n".join(lines)


class TestErrorModulesDoNotImportBlockModules:
    """ERROR modules should not import from BLOCK modules."""

    @pytest.fixture
    def error_files(self) -> list[Path]:
        """Get all error-related files in exceptions/ and services/."""
        files: list[Path] = []
        # exceptions/error_*.py
        exceptions_dir = PROJECT_ROOT / "src/vibe3/exceptions"
        files.extend(exceptions_dir.glob("error_*.py"))
        # services/error_tracking_*.py
        services_dir = PROJECT_ROOT / "src/vibe3/services"
        files.extend(services_dir.glob("error_tracking_*.py"))
        assert files, (
            f"No error files found. Check paths: "
            f"{exceptions_dir}/error_*.py, {services_dir}/error_tracking_*.py"
        )
        return files

    def test_error_modules_do_not_import_flow_service(
        self, error_files: list[Path]
    ) -> None:
        """ERROR modules should not import FlowService."""
        for file_path in error_files:
            content = get_file_content(file_path)
            assert (
                "FlowService" not in content
            ), f"{file_path.name} imports FlowService (BLOCK module)"

    def test_error_modules_do_not_import_block_flow(
        self, error_files: list[Path]
    ) -> None:
        """ERROR modules should not import block_flow."""
        for file_path in error_files:
            content = get_file_content(file_path)
            # Exclude Literal["record_only"] false positive
            lines = content.split("\n")
            for line in lines:
                if 'Literal["record_only"]' in line:
                    continue
                assert (
                    "block_flow" not in line
                ), f"{file_path.name} references block_flow (BLOCK module)"

    def test_error_modules_do_not_import_fail_issue(
        self, error_files: list[Path]
    ) -> None:
        """ERROR modules should not import fail_issue."""
        for file_path in error_files:
            content = get_file_content(file_path)
            assert (
                "fail_issue" not in content
            ), f"{file_path.name} imports fail_issue (BLOCK module)"

    def test_error_modules_do_not_import_blocked_state(
        self, error_files: list[Path]
    ) -> None:
        """ERROR modules should not import blocked_state modules."""
        for file_path in error_files:
            content = get_file_content(file_path)
            assert (
                "blocked_state" not in content
            ), f"{file_path.name} imports blocked_state (BLOCK module)"


class TestBlockModulesDoNotImportErrorModules:
    """BLOCK modules should not import from ERROR modules."""

    @pytest.fixture
    def block_files(self) -> list[Path]:
        """Get all BLOCK-related files in services/."""
        services_dir = PROJECT_ROOT / "src/vibe3/services"
        files: list[Path] = []
        # Glob for blocked_state files and flow_block files
        files.extend(services_dir.glob("*blocked_state*.py"))
        files.extend(services_dir.glob("flow_block_*.py"))
        assert files, (
            f"No block files found. Check path: {services_dir}/"
            f"*blocked_state*.py, flow_block_*.py"
        )
        return files

    def test_block_modules_do_not_import_error_tracking_service(
        self, block_files: list[Path]
    ) -> None:
        """BLOCK modules should not import ErrorTrackingService."""
        for file_path in block_files:
            content = get_file_content(file_path)
            assert (
                "ErrorTrackingService" not in content
            ), f"{file_path.name} imports ErrorTrackingService (ERROR module)"

    def test_block_modules_do_not_reference_error_log(
        self, block_files: list[Path]
    ) -> None:
        """BLOCK modules should not reference error_log in code (docstrings OK)."""
        for file_path in block_files:
            content = get_file_content(file_path)
            code_only = strip_docstrings_and_comments(content)
            assert (
                "error_log" not in code_only
            ), f"{file_path.name} references error_log (ERROR module) in code"

    def test_block_modules_do_not_import_record_error(
        self, block_files: list[Path]
    ) -> None:
        """BLOCK modules should not import record_error helper."""
        for file_path in block_files:
            content = get_file_content(file_path)
            if "from vibe3.services.shared.errors import record_error" in content:
                pytest.fail(
                    f"{file_path.name} imports record_error "
                    f"from services.shared.errors (ERROR module)"
                )
