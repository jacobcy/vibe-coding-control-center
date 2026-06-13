"""Tests for VibeConfig._expand_config_variables and _load_supplementary."""

from __future__ import annotations

from pathlib import Path

import pytest

from vibe3.config.settings import (
    PathsConfig,
    VibeConfig,
    get_commands_root,
    get_source_root,
)


class TestPathsConfig:
    """Tests for PathsConfig model and helper functions."""

    def test_paths_config_is_public_config_api(self) -> None:
        """PathsConfig is exported through vibe3.config public API."""
        from vibe3.config import PathsConfig as PublicPathsConfig

        assert PublicPathsConfig is PathsConfig

    def test_paths_config_defaults(self) -> None:
        """PathsConfig() produces correct defaults."""
        pc = PathsConfig()
        assert pc.vibe3_root == "src/vibe3"
        assert pc.commands_root == "src/vibe3/commands"
        assert pc.policies_root == "supervisor/policies"

    def test_paths_config_custom_vibe3_root(self) -> None:
        """VibeConfig with custom paths works."""
        vc = VibeConfig(paths=PathsConfig(vibe3_root="custom/src"))
        assert vc.paths.vibe3_root == "custom/src"
        assert vc.paths.commands_root == "src/vibe3/commands"  # unchanged default

    def test_paths_config_custom_all(self) -> None:
        """VibeConfig with all custom paths works."""
        vc = VibeConfig(
            paths=PathsConfig(
                vibe3_root="custom/src",
                commands_root="custom/src/commands",
                policies_root="custom/policies",
            )
        )
        assert vc.paths.vibe3_root == "custom/src"
        assert vc.paths.commands_root == "custom/src/commands"

    def test_get_source_root_default(self) -> None:
        """get_source_root() returns default via config."""
        root = get_source_root()
        assert root == "src/vibe3"

    def test_get_commands_root_default(self) -> None:
        """get_commands_root() returns default via config."""
        root = get_commands_root()
        assert root == "src/vibe3/commands"

    def test_dag_service_uses_custom_source_root(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """build_module_graph() uses configured source root."""
        from vibe3.analysis.dag_service import DAGError, build_module_graph

        # Set custom source root by patching get_config
        custom_root = "custom/src/vibe3"
        custom_config = VibeConfig(paths=PathsConfig(vibe3_root=custom_root))
        monkeypatch.setattr("vibe3.config.loader.get_config", lambda: custom_config)

        # Should fail because custom path doesn't exist, proving it tried to use it
        with pytest.raises(DAGError) as exc_info:
            build_module_graph()

        assert custom_root in str(exc_info.value)

    def test_coverage_service_categorize_uses_custom_source_root(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_categorize_by_layer uses configured source root."""
        from vibe3.analysis.coverage_service import CoverageService

        # Set custom source root by patching get_config
        custom_root = "custom/src"
        custom_config = VibeConfig(paths=PathsConfig(vibe3_root=custom_root))
        monkeypatch.setattr("vibe3.config.loader.get_config", lambda: custom_config)

        service = CoverageService()
        coverage_data = {
            "files": {
                f"{custom_root}/services/flow_service.py": {"summary": {}},
                "src/vibe3/services/other_service.py": {"summary": {}},
            }
        }

        categorized = service._categorize_by_layer(
            coverage_data, ("services", "clients")
        )

        # Only file under custom_root should be categorized
        assert f"{custom_root}/services/flow_service.py" in categorized["services"]
        assert "src/vibe3/services/other_service.py" not in categorized["services"]

    def test_is_v3_source_file_uses_custom_source_root(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """is_v3_source_file uses configured source root prefix."""
        from vibe3.analysis.change_scope_service import is_v3_source_file

        # Set custom source root by patching get_config
        custom_root = "custom/src"
        custom_config = VibeConfig(paths=PathsConfig(vibe3_root=custom_root))
        monkeypatch.setattr("vibe3.config.loader.get_config", lambda: custom_config)

        # Should return True for custom_root path
        assert is_v3_source_file(f"{custom_root}/services/flow_service.py")
        # Should return False for default path
        assert not is_v3_source_file("src/vibe3/services/flow_service.py")

    def test_command_analyzer_uses_custom_commands_root(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """analyze_command() uses configured commands root."""
        from vibe3.analysis.command_analyzer import (
            CommandAnalyzerError,
            analyze_command,
        )

        # Set custom commands root by patching get_config
        custom_root = "custom/commands"
        custom_config = VibeConfig(paths=PathsConfig(commands_root=custom_root))
        monkeypatch.setattr("vibe3.config.loader.get_config", lambda: custom_config)

        # Should fail because custom path doesn't exist, proving it tried to use it
        with pytest.raises(CommandAnalyzerError) as exc_info:
            analyze_command("flow")

        assert "Command file not found" in str(exc_info.value)


class TestExpandConfigVariables:
    """Smoke tests: _expand_config_variables delegates to expand_config_variables."""

    def test_expand_config_variables_simple(self) -> None:
        config = {"paths": {"root": "/app"}, "file": "${paths.root}/data"}
        result = VibeConfig._expand_config_variables(config)
        assert result["file"] == "/app/data"

    def test_expand_config_variables_cycle(self) -> None:
        """Circular references terminate without hanging."""
        config = {"a": "${b}", "b": "${a}"}
        result = VibeConfig._expand_config_variables(config)
        assert result["a"] == "${b}"
        assert result["b"] == "${a}"


class TestLoadSupplementaryPromptsRoot:
    """Tests for prompts_root path resolution in VibeConfig._load_supplementary."""

    def test_prompts_root_from_paths_config_takes_priority(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """paths.prompts_root in data overrides repo-local fallback paths."""
        prompts_dir = tmp_path / "assets" / "prompts"
        prompts_dir.mkdir(parents=True)
        prompts_file = prompts_dir / "prompts.yaml"
        # Use a valid _PROMPT_KEYS key: agent_prompt.global_notice
        prompts_file.write_text("agent_prompt:\n  global_notice: installed-notice\n")

        # Run from tmp_path so repo-local prompts paths do not exist
        monkeypatch.chdir(tmp_path)
        data: dict = {"paths": {"prompts_root": str(prompts_dir)}}

        result = VibeConfig._load_supplementary(data)

        assert result.get("agent_prompt", {}).get("global_notice") == "installed-notice"

    def test_prompts_root_absent_falls_back_to_repo_local(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When paths.prompts_root is absent, no prompts merge occurs."""
        monkeypatch.chdir(tmp_path)
        data: dict = {}

        result = VibeConfig._load_supplementary(data)

        # No prompts merged — agent_prompt should not appear
        assert "agent_prompt" not in result

    def test_prompts_root_set_but_prompts_yaml_missing_falls_back(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """paths.prompts_root present but prompts.yaml missing → no merge."""
        missing_dir = tmp_path / "missing"
        # Do not create the directory or file
        monkeypatch.chdir(tmp_path)

        data: dict = {"paths": {"prompts_root": str(missing_dir)}}

        result = VibeConfig._load_supplementary(data)

        assert "agent_prompt" not in result

    def test_empty_prompts_root_falls_back(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Empty string paths.prompts_root is treated as falsy and falls back."""
        # Run from tmp_path so repo-local prompts paths do not exist
        monkeypatch.chdir(tmp_path)
        data: dict = {"paths": {"prompts_root": ""}}

        result = VibeConfig._load_supplementary(data)

        # Empty string should be treated as falsy and not attempt path resolution
        assert "agent_prompt" not in result
