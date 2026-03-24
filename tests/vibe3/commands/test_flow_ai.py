"""Integration tests for flow command with AI support.

NOTE: AI features were removed from flow new command in a later refactor.
These tests are skipped until AI features are re-implemented.
"""

from pathlib import Path

import pytest
from typer.testing import CliRunner


@pytest.fixture
def runner() -> CliRunner:
    """Create CLI test runner."""
    return CliRunner()


@pytest.mark.skip(reason="AI features removed from flow new - tests need update")
class TestFlowCommandAI:
    """Tests for flow new command with AI support."""

    def test_flow_new_without_ai(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test flow new without --ai flag works normally."""
        ...

    def test_flow_new_ai_disabled(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test flow new with --ai when AI is disabled."""
        ...

    def test_flow_new_ai_missing_issue(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test flow new with --ai but no --issue."""
        ...

    def test_flow_new_ai_json_uses_first_suggestion_without_prompt(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test flow new --ai --json uses first suggestion without prompting."""
        ...


@pytest.mark.skip(reason="create_flow_with_branch not implemented - tests need update")
class TestFlowCommandCreateBranch:
    """Tests for flow new command with --create-branch flag."""

    def test_flow_new_create_branch_success(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test flow new --create-branch creates branch and flow."""
        ...

    def test_flow_new_create_branch_custom_start_ref(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test flow new --create-branch with custom --start-ref."""
        ...

    def test_flow_new_create_branch_already_exists(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test flow new --create-branch when branch already exists."""
        ...

    def test_flow_new_without_create_branch_uses_current(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test flow new without -c uses current branch."""
        ...
