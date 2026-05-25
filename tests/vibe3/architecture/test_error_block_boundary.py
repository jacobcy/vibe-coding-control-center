"""Architecture boundary tests: ERROR and BLOCK modules must stay decoupled."""

from pathlib import Path

import pytest


def get_file_content(file_path: Path) -> str:
    """Read file content, return empty string if not exists."""
    if not file_path.exists():
        return ""
    return file_path.read_text(encoding="utf-8")


class TestErrorModulesDoNotImportBlockModules:
    """ERROR modules should not import from BLOCK modules."""

    @pytest.fixture
    def error_files(self) -> list[Path]:
        """Get all error-related files in exceptions/."""
        exceptions_dir = Path("src/vibe3/exceptions")
        error_files = list(exceptions_dir.glob("error_*.py"))
        return error_files

    def test_error_modules_do_not_import_flow_service(self, error_files):
        """ERROR modules should not import FlowService."""
        for file_path in error_files:
            content = get_file_content(file_path)
            assert (
                "FlowService" not in content
            ), f"{file_path.name} imports FlowService (BLOCK module)"

    def test_error_modules_do_not_import_block_flow(self, error_files):
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

    def test_error_modules_do_not_import_fail_issue(self, error_files):
        """ERROR modules should not import fail_issue."""
        for file_path in error_files:
            content = get_file_content(file_path)
            assert (
                "fail_issue" not in content
            ), f"{file_path.name} imports fail_issue (BLOCK module)"

    def test_error_modules_do_not_import_blocked_state(self, error_files):
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
        services_dir = Path("src/vibe3/services")
        block_files = []
        # Add blocked_state files
        block_files.extend(services_dir.glob("*blocked_state*.py"))
        # Add flow_block_mixin
        flow_block = services_dir / "flow_block_mixin.py"
        if flow_block.exists():
            block_files.append(flow_block)
        return block_files

    def test_block_modules_do_not_import_error_tracking_service(self, block_files):
        """BLOCK modules should not import ErrorTrackingService."""
        for file_path in block_files:
            content = get_file_content(file_path)
            assert (
                "ErrorTrackingService" not in content
            ), f"{file_path.name} imports ErrorTrackingService (ERROR module)"

    def test_block_modules_do_not_import_error_log(self, block_files):
        """BLOCK modules should not reference error_log table directly."""
        for file_path in block_files:
            content = get_file_content(file_path)
            # Exclude docstring references to "error_log" table
            lines = content.split("\n")
            in_docstring = False
            for i, line in enumerate(lines):
                stripped = line.strip()
                # Track docstring state
                if stripped.startswith('"""') or stripped.startswith("'''"):
                    # Toggle docstring state
                    in_docstring = not in_docstring
                    # Handle single-line docstrings
                    if stripped.count('"""') >= 2 or stripped.count("'''") >= 2:
                        in_docstring = False
                    continue
                # Skip lines inside docstrings or comments
                if in_docstring or stripped.startswith("#"):
                    continue
                assert (
                    "error_log" not in line
                ), f"{file_path.name}:{i+1} references error_log (ERROR module)"

    def test_block_modules_do_not_import_record_error(self, block_files):
        """BLOCK modules should not import record_error helper."""
        for file_path in block_files:
            content = get_file_content(file_path)
            # Check import statements specifically
            if "from vibe3.exceptions.error_helpers import record_error" in content:
                pytest.fail(
                    f"{file_path.name} imports record_error "
                    f"from error_helpers (ERROR module)"
                )
            if "from vibe3.exceptions import record_error" in content:
                pytest.fail(
                    f"{file_path.name} imports record_error "
                    f"from exceptions (ERROR module)"
                )
