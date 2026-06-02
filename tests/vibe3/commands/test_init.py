"""Tests for init command."""

from pathlib import Path

from typer.testing import CliRunner

from vibe3.commands.init import app as init_app

runner = CliRunner()


class TestInitCommand:
    """Tests for init CLI command."""

    def test_init_creates_vibe_config(self, tmp_path: Path) -> None:
        """Test init creates .vibe/config.yaml."""
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(init_app, [])

            assert result.exit_code == 0
            config_path = tmp_path / ".vibe" / "config.yaml"
            assert config_path.exists()
            content = config_path.read_text()
            assert "profile: default" in content
            assert "adapter: default" in content
        finally:
            os.chdir(original_cwd)

    def test_init_skips_existing_config(self, tmp_path: Path) -> None:
        """Test init skips if .vibe/config.yaml already exists."""
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            # Create existing config
            vibe_dir = tmp_path / ".vibe"
            vibe_dir.mkdir()
            config_path = vibe_dir / "config.yaml"
            original_content = "profile: custom\nadapter: custom\n"
            config_path.write_text(original_content)

            result = runner.invoke(init_app, [])

            assert result.exit_code == 0
            # Verify original content preserved
            assert config_path.read_text() == original_content
            assert "already exists" in result.output
        finally:
            os.chdir(original_cwd)

    def test_init_creates_gitignore(self, tmp_path: Path) -> None:
        """Test init creates .gitignore if it doesn't exist."""
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(init_app, [])

            assert result.exit_code == 0
            gitignore_path = tmp_path / ".gitignore"
            assert gitignore_path.exists()
            content = gitignore_path.read_text()
            assert ".vibe/" in content
            assert ".worktrees/" in content
            assert ".agent/plans/" in content
            assert ".agent/reports/" in content
            assert "temp/" in content
        finally:
            os.chdir(original_cwd)

    def test_init_appends_gitignore_entries(self, tmp_path: Path) -> None:
        """Test init appends missing entries to existing .gitignore."""
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            # Create gitignore with some entries
            gitignore_path = tmp_path / ".gitignore"
            gitignore_path.write_text(".vibe/\n*.pyc\n")

            result = runner.invoke(init_app, [])

            assert result.exit_code == 0
            content = gitignore_path.read_text()
            # Original entry preserved
            assert ".vibe/" in content
            assert "*.pyc" in content
            # Missing entries added
            assert ".worktrees/" in content
            assert "temp/" in content
            assert "Added" in result.output
        finally:
            os.chdir(original_cwd)

    def test_init_skips_gitignore_when_all_present(self, tmp_path: Path) -> None:
        """Test init doesn't modify .gitignore if all entries present."""
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            # Create gitignore with all vibe3 entries
            gitignore_path = tmp_path / ".gitignore"
            gitignore_path.write_text(
                ".vibe/\n.worktrees/\n.agent/plans/\n.agent/reports/\ntemp/\n"
            )

            result = runner.invoke(init_app, [])

            assert result.exit_code == 0
            # Should not add duplicates
            content = gitignore_path.read_text()
            assert content.count(".vibe/") == 1
            assert "already has all entries" in result.output
        finally:
            os.chdir(original_cwd)

    def test_init_creates_agents_md(self, tmp_path: Path) -> None:
        """Test init creates AGENTS.md if it doesn't exist."""
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(init_app, [])

            assert result.exit_code == 0
            agents_path = tmp_path / "AGENTS.md"
            assert agents_path.exists()
            content = agents_path.read_text()
            assert "# AI Agent Guide" in content
            assert "vibe-coding-control-center" in content
        finally:
            os.chdir(original_cwd)

    def test_init_skips_existing_agents_md(self, tmp_path: Path) -> None:
        """Test init skips if AGENTS.md already exists."""
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            # Create existing AGENTS.md
            agents_path = tmp_path / "AGENTS.md"
            original_content = "# My Project\nCustom content\n"
            agents_path.write_text(original_content)

            result = runner.invoke(init_app, [])

            assert result.exit_code == 0
            # Verify original content preserved
            assert agents_path.read_text() == original_content
            assert "already exists" in result.output
        finally:
            os.chdir(original_cwd)

    def test_init_outputs_next_steps(self, tmp_path: Path) -> None:
        """Test init outputs next steps including vibe-project-check."""
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(init_app, [])

            assert result.exit_code == 0
            assert "/vibe-project-check" in result.output
            assert "VIBE_MANAGER_GITHUB_TOKEN" in result.output
            assert "vibe3 serve" in result.output
            assert "initialized successfully" in result.output
        finally:
            os.chdir(original_cwd)
