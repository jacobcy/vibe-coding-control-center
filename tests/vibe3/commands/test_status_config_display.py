"""Tests for status command configuration display enhancements."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.commands.status import _analyze_orchestra_config_sources
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.services.orchestra.status import OrchestraSnapshot

runner = CliRunner(env={"NO_COLOR": "1"})


class TestAnalyzeOrchestraConfigSources:
    """Tests for _analyze_orchestra_config_sources function."""

    def test_all_fields_default(self, monkeypatch) -> None:
        """When config matches Pydantic defaults, all sources are 'default'."""
        monkeypatch.delenv("MANAGER_USERNAMES", raising=False)
        config = OrchestraConfig()
        sources = _analyze_orchestra_config_sources(config)

        assert sources["max_concurrent_flows"] == "default"
        assert sources["polling_interval"] == "default"
        assert sources["debug_polling_interval"] == "default"
        assert sources["scene_base_ref"] == "default"
        assert sources["repo"] == "default"
        assert sources["manager_usernames"] == "default"

    def test_config_override_detection(self) -> None:
        """Fields that differ from defaults are marked as 'config override'."""
        config = OrchestraConfig(
            max_concurrent_flows=5,  # default is 3
            polling_interval=300,  # default is 900
        )
        sources = _analyze_orchestra_config_sources(config)

        assert sources["max_concurrent_flows"] == "config override"
        assert sources["polling_interval"] == "config override"
        # Other fields still default
        assert sources["debug_polling_interval"] == "default"
        assert sources["scene_base_ref"] == "default"

    def test_env_override_detection(self) -> None:
        """When env var is set, field is marked as 'env override'."""
        with patch.dict(os.environ, {"MANAGER_USERNAMES": "custom-manager"}):
            config = OrchestraConfig()
            sources = _analyze_orchestra_config_sources(config)

            # manager_usernames should be detected as env override
            assert sources["manager_usernames"] == "env override"

    def test_env_override_takes_precedence(self) -> None:
        """Env override takes precedence over config override."""
        with patch.dict(os.environ, {"MANAGER_USERNAMES": "env-manager"}):
            # Config has a non-default value
            config = OrchestraConfig(manager_usernames=("config-manager",))
            sources = _analyze_orchestra_config_sources(config)

            # Env var should win
            assert sources["manager_usernames"] == "env override"


class TestRenderConfigurationOutput:
    """Tests for _render_configuration output format."""

    @patch("vibe3.services.orchestra.helpers.get_manager_usernames")
    @patch("vibe3.config.orchestra_settings.load_orchestra_config")
    @patch("vibe3.services.orchestra.status.OrchestraStatusService.fetch_live_snapshot")
    def test_configuration_shows_source_annotations(
        self,
        mock_fetch_live_snapshot: MagicMock,
        mock_load_orchestra_config: MagicMock,
        mock_get_manager_usernames: MagicMock,
    ) -> None:
        """Configuration output should include source annotations."""
        config = OrchestraConfig()
        mock_load_orchestra_config.return_value = config
        mock_get_manager_usernames.return_value = ["vibe-manager-agent"]
        mock_fetch_live_snapshot.return_value = OrchestraSnapshot(
            timestamp=1234567890.0,
            server_running=True,
            active_issues=tuple(),
            active_flows=0,
            active_worktrees=0,
        )

        with patch("pathlib.Path.exists", return_value=False):
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        # Check for default annotations
        assert "(default)" in result.output
        # Check for Configuration Sources section
        assert "Configuration Sources:" in result.output

    @patch("vibe3.services.orchestra.helpers.get_manager_usernames")
    @patch("vibe3.config.orchestra_settings.load_orchestra_config")
    @patch("vibe3.services.orchestra.status.OrchestraStatusService.fetch_live_snapshot")
    def test_configuration_shows_debug_mode(
        self,
        mock_fetch_live_snapshot: MagicMock,
        mock_load_orchestra_config: MagicMock,
        mock_get_manager_usernames: MagicMock,
    ) -> None:
        """Configuration output should show debug mode status."""
        config = OrchestraConfig(debug=False)
        mock_load_orchestra_config.return_value = config
        mock_get_manager_usernames.return_value = ["vibe-manager-agent"]
        mock_fetch_live_snapshot.return_value = OrchestraSnapshot(
            timestamp=1234567890.0,
            server_running=True,
            active_issues=tuple(),
            active_flows=0,
            active_worktrees=0,
        )

        with patch("pathlib.Path.exists", return_value=False):
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        # Check for debug mode line
        assert "Debug mode:" in result.output
        assert "OFF" in result.output

    @patch("vibe3.services.orchestra.helpers.get_manager_usernames")
    @patch("vibe3.config.orchestra_settings.load_orchestra_config")
    @patch("vibe3.services.orchestra.status.OrchestraStatusService.fetch_live_snapshot")
    def test_status_shows_orchestra_and_config_sections(
        self,
        mock_fetch_live_snapshot: MagicMock,
        mock_load_orchestra_config: MagicMock,
        mock_get_manager_usernames: MagicMock,
    ) -> None:
        """vibe status should show both Orchestra Status and Vibe3 Configuration."""
        config = OrchestraConfig()
        mock_load_orchestra_config.return_value = config
        mock_get_manager_usernames.return_value = ["vibe-manager-agent"]
        mock_fetch_live_snapshot.return_value = OrchestraSnapshot(
            timestamp=1234567890.0,
            server_running=True,
            active_issues=tuple(),
            active_flows=0,
            active_worktrees=0,
        )

        with patch("pathlib.Path.exists", return_value=False):
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "Orchestra Status" in result.output
        assert "Vibe3 Configuration" in result.output

    @patch("vibe3.services.orchestra.status.OrchestraStatusService.fetch_live_snapshot")
    def test_status_uses_keys_env_manager_when_token_already_exists(
        self,
        mock_fetch_live_snapshot: MagicMock,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """keys.env should still fill MANAGER_USERNAMES when another key is set."""
        (tmp_path / "config").mkdir()
        (tmp_path / "config" / "keys.env").write_text(
            "VIBE_MANAGER_GITHUB_TOKEN=from-file\n" "MANAGER_USERNAMES=keys-manager\n",
            encoding="utf-8",
        )
        (tmp_path / "config" / "v3").mkdir(parents=True)
        (tmp_path / "config" / "v3" / "settings.yaml").write_text(
            "orchestra:\n"
            "  repo: test/repo\n"
            "  manager_usernames:\n"
            "    - config-manager\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("VIBE_MANAGER_GITHUB_TOKEN", "existing-token")
        monkeypatch.delenv("MANAGER_USERNAMES", raising=False)

        mock_fetch_live_snapshot.return_value = OrchestraSnapshot(
            timestamp=1234567890.0,
            server_running=True,
            active_issues=tuple(),
            active_flows=0,
            active_worktrees=0,
        )

        from vibe3.utils.git_helpers import find_repo_root as _impl

        _impl.cache_clear()
        with patch("vibe3.utils.git_helpers.find_repo_root", return_value=tmp_path):
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "Manager agents:    keys-manager (env override)" in result.output


class TestTaskStatusExcludesSystemStatus:
    """Tests that task status does not show system status sections."""

    @patch("vibe3.services.orchestra.helpers.get_manager_usernames")
    @patch("vibe3.config.orchestra_settings.load_orchestra_config")
    @patch("vibe3.services.orchestra.status.OrchestraStatusService.fetch_live_snapshot")
    @patch("vibe3.services.task.status.FlowService")
    @patch("vibe3.services.task.status.StatusQueryService")
    def test_task_status_no_system_sections(
        self,
        mock_status_service_cls: MagicMock,
        mock_flow_service_cls: MagicMock,
        mock_fetch_live_snapshot: MagicMock,
        mock_load_orchestra_config: MagicMock,
        mock_get_manager_usernames: MagicMock,
    ) -> None:
        """vibe task status should not show Orchestra Status or Vibe3 Configuration."""
        config_mock = MagicMock()
        config_mock.repo = "test/repo"
        config_mock.pid_file = "/tmp/vibe3.pid"
        mock_load_orchestra_config.return_value = config_mock
        mock_get_manager_usernames.return_value = ["manager-bot"]
        mock_fetch_live_snapshot.return_value = OrchestraSnapshot(
            timestamp=1234567890.0,
            server_running=True,
            active_issues=tuple(),
            active_flows=0,
            active_worktrees=0,
        )

        flow_service = MagicMock()
        flow_service.list_flows.return_value = []
        mock_flow_service_cls.return_value = flow_service

        status_service = MagicMock()
        status_service.fetch_worktree_map.return_value = {}
        status_service.fetch_orchestrated_issues.return_value = []
        mock_status_service_cls.return_value = status_service

        result = runner.invoke(app, ["task", "status"])

        assert result.exit_code == 0
        # Verify Orchestra Status and Vibe3 Configuration are NOT in output
        assert "Orchestra Status" not in result.output
        assert "Vibe3 Configuration" not in result.output
