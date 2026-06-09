"""Tests for centralized environment variable override framework."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from vibe3.config.env_override import (
    OVERRIDE_RULES,
    EnvOverrideRule,
    apply_env_overrides,
    get_env_override,
)
from vibe3.config.loader import load_keys_env_fallback
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.services.orchestra.helpers import get_manager_usernames


def _mock_repo_root_not_found() -> Path:
    """Simulate find_repo_root() when not in a git repository."""
    raise SystemError("Cannot resolve repository root — not inside a git repository")


class TestEnvOverrideRule:
    """Test EnvOverrideRule dataclass."""

    def test_rule_creation(self) -> None:
        """Test creating an override rule."""
        rule = EnvOverrideRule(
            env_key="TEST_KEY",
            config_path="test.path",
            converter=int,
            description="Test rule",
        )
        assert rule.env_key == "TEST_KEY"
        assert rule.config_path == "test.path"
        assert rule.converter is int
        assert rule.description == "Test rule"

    def test_default_converter(self) -> None:
        """Test default converter is str."""
        rule = EnvOverrideRule(env_key="KEY", config_path="path")
        assert rule.converter is str


class TestApplyEnvOverrides:
    """Test apply_env_overrides function."""

    def test_apply_simple_override(self) -> None:
        """Test applying a simple override."""
        config = {"orchestra": {"manager_usernames": ["default"]}}

        with patch.dict(os.environ, {"MANAGER_USERNAMES": "custom-manager"}):
            result = apply_env_overrides(config)

        assert result["orchestra"]["manager_usernames"] == ("custom-manager",)

    def test_apply_int_override(self) -> None:
        """Test applying an integer override."""
        config = {"code_limits": {"total_file_loc": {"v2_shell": 4000}}}

        with patch.dict(os.environ, {"VIBE_CODE_LIMITS_V2_SHELL_TOTAL_LOC": "5000"}):
            result = apply_env_overrides(config)

        assert result["code_limits"]["total_file_loc"]["v2_shell"] == 5000

    def test_apply_tuple_override(self) -> None:
        """Test applying a tuple override with comma-separated values."""
        config = {"orchestra": {"manager_usernames": []}}

        with patch.dict(
            os.environ, {"MANAGER_USERNAMES": "manager1,manager2,manager3"}
        ):
            result = apply_env_overrides(config)

        assert result["orchestra"]["manager_usernames"] == (
            "manager1",
            "manager2",
            "manager3",
        )

    def test_invalid_env_value_logs_warning(self) -> None:
        """Test that invalid values log warnings but don't crash."""
        from loguru import logger

        warnings_captured: list[str] = []
        handler_id = logger.add(
            lambda msg: warnings_captured.append(str(msg)), level="WARNING"
        )
        try:
            config = {"code_limits": {"total_file_loc": {"v2_shell": 4000}}}
            with patch.dict(
                os.environ, {"VIBE_CODE_LIMITS_V2_SHELL_TOTAL_LOC": "invalid"}
            ):
                result = apply_env_overrides(config)
        finally:
            logger.remove(handler_id)

        assert result["code_limits"]["total_file_loc"]["v2_shell"] == 4000
        assert any("Invalid env value" in w for w in warnings_captured)

    def test_missing_env_key_no_change(self) -> None:
        """Test that missing env key doesn't change config."""
        config = {"orchestra": {"manager_usernames": ["default"]}}

        # Ensure MANAGER_USERNAMES is not set
        os.environ.pop("MANAGER_USERNAMES", None)

        result = apply_env_overrides(config)

        assert result["orchestra"]["manager_usernames"] == ["default"]

    def test_custom_rules(self) -> None:
        """Test applying custom rules."""
        config = {"custom": {"setting": "default"}}

        custom_rules = [
            EnvOverrideRule(
                env_key="CUSTOM_SETTING",
                config_path="custom.setting",
            )
        ]

        with patch.dict(os.environ, {"CUSTOM_SETTING": "overridden"}):
            result = apply_env_overrides(config, rules=custom_rules)

        assert result["custom"]["setting"] == "overridden"


class TestGetEnvOverride:
    """Test get_env_override convenience function."""

    def test_get_with_default_converter(self) -> None:
        """Test getting env var with default string converter."""
        with patch.dict(os.environ, {"TEST_KEY": "value"}):
            result = get_env_override("TEST_KEY")
        assert result == "value"

    def test_get_with_custom_converter(self) -> None:
        """Test getting env var with custom converter."""
        with patch.dict(os.environ, {"TEST_INT": "42"}):
            result = get_env_override("TEST_INT", converter=int)
        assert result == 42

    def test_get_with_default_value(self) -> None:
        """Test getting env var with default value."""
        os.environ.pop("MISSING_KEY", None)
        result = get_env_override("MISSING_KEY", default="default")
        assert result == "default"

    def test_invalid_value_returns_default(self) -> None:
        """Test that invalid values return default."""
        with patch.dict(os.environ, {"INVALID_INT": "not-a-number"}):
            result = get_env_override("INVALID_INT", converter=int, default=0)
        assert result == 0


class TestLoadKeysEnvFallback:
    """Test load_keys_env_fallback function."""

    def test_loads_missing_manager_usernames_when_token_already_set(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Existing token env must not prevent keys.env from supplying managers."""
        keys_file = tmp_path / "config" / "keys.env"
        keys_file.parent.mkdir(parents=True, exist_ok=True)
        keys_file.write_text(
            "VIBE_MANAGER_GITHUB_TOKEN=from-file\n" "MANAGER_USERNAMES=keys-manager\n"
        )

        monkeypatch.setattr(
            "vibe3.utils.git_helpers.find_repo_root",
            lambda: tmp_path,
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("VIBE_MANAGER_GITHUB_TOKEN", "existing-token")
        monkeypatch.delenv("MANAGER_USERNAMES", raising=False)

        load_keys_env_fallback()

        assert os.environ.get("VIBE_MANAGER_GITHUB_TOKEN") == "existing-token"
        assert os.environ.get("MANAGER_USERNAMES") == "keys-manager"

    def test_load_from_project_keys(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test loading from project config/keys.env."""
        # Create temporary keys.env
        keys_content = "TEST_KEY=test_value\n"
        keys_file = tmp_path / "config" / "keys.env"
        keys_file.parent.mkdir(parents=True, exist_ok=True)
        keys_file.write_text(keys_content)

        # Mock find_repo_root to return tmp_path (simulating repo root)
        from vibe3.utils.git_helpers import find_repo_root

        monkeypatch.setattr(find_repo_root, "cache_clear", lambda: None)
        monkeypatch.setattr(
            "vibe3.utils.git_helpers.find_repo_root",
            lambda: tmp_path,
        )

        # Change to temp directory
        monkeypatch.chdir(tmp_path)

        # Clear existing env vars
        os.environ.pop("VIBE_MANAGER_GITHUB_TOKEN", None)
        os.environ.pop("MANAGER_USERNAMES", None)
        os.environ.pop("GH_TOKEN", None)

        load_keys_env_fallback()

        assert os.environ.get("TEST_KEY") == "test_value"

    def test_warns_when_repo_root_undetectable_and_cwd_path_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test WARNING emitted when repo root cannot be detected.

        Verifies WARNING is emitted when repo root detection fails and CWD
        has no config/keys.env file.
        """
        from loguru import logger

        warnings_captured: list[str] = []
        handler_id = logger.add(
            lambda msg: warnings_captured.append(str(msg)), level="WARNING"
        )

        try:
            # Mock find_repo_root to raise SystemError (not in git repo)
            monkeypatch.setattr(
                "vibe3.utils.git_helpers.find_repo_root",
                _mock_repo_root_not_found,
            )
            # Ensure no home-dir keys.env interferes
            monkeypatch.setattr(Path, "home", lambda: tmp_path)
            # chdir to tmp_path (no config/keys.env here)
            monkeypatch.chdir(tmp_path)

            os.environ.pop("VIBE_MANAGER_GITHUB_TOKEN", None)
            os.environ.pop("MANAGER_USERNAMES", None)

            load_keys_env_fallback()

            assert any("Cannot detect repo root" in w for w in warnings_captured)
        finally:
            logger.remove(handler_id)

    def test_loads_from_repo_root_when_cwd_differs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test keys.env found via repo root even when CWD is a subdirectory."""
        # Create keys.env in tmp_path (repo root)
        keys_file = tmp_path / "config" / "keys.env"
        keys_file.parent.mkdir(parents=True, exist_ok=True)
        keys_file.write_text("REPO_KEY=from_repo_root\n")

        # Create subdirectory and chdir into it (no config/keys.env there)
        subdir = tmp_path / "src" / "vibe3"
        subdir.mkdir(parents=True, exist_ok=True)
        monkeypatch.chdir(subdir)

        # Mock find_repo_root to return tmp_path
        monkeypatch.setattr(
            "vibe3.utils.git_helpers.find_repo_root",
            lambda: tmp_path,
        )

        os.environ.pop("VIBE_MANAGER_GITHUB_TOKEN", None)
        os.environ.pop("MANAGER_USERNAMES", None)
        os.environ.pop("REPO_KEY", None)

        load_keys_env_fallback()

        assert os.environ.get("REPO_KEY") == "from_repo_root"


class TestGetManagerUsernames:
    """Test get_manager_usernames reads config (env overrides applied at load time)."""

    def test_config_value_returned(self) -> None:
        """Test that config value is returned directly."""
        config = OrchestraConfig(manager_usernames=("config-manager",))
        result = get_manager_usernames(config)
        assert result == ("config-manager",)

    def test_env_override_reflected_when_pre_applied(self) -> None:
        """Test that an env-overridden config value is used correctly.

        Env overrides are applied at config load time (via apply_env_overrides /
        get_config_with_env_override). Callers should pass a config that was loaded
        through that path; get_manager_usernames does not re-read env vars.
        """
        # Simulate a config that was loaded with MANAGER_USERNAMES=env-manager
        config = OrchestraConfig(manager_usernames=("env-manager",))
        result = get_manager_usernames(config)
        assert result == ("env-manager",)

    def test_multiple_usernames_from_config(self) -> None:
        """Test multiple usernames returned from config tuple."""
        config = OrchestraConfig(manager_usernames=("manager1", "manager2", "manager3"))
        result = get_manager_usernames(config)
        assert result == ("manager1", "manager2", "manager3")


class TestOverrideRulesRegistry:
    """Test OVERRIDE_RULES registry completeness."""

    def test_override_rules_not_empty(self) -> None:
        """Test that override rules are defined."""
        assert len(OVERRIDE_RULES) > 0

    def test_all_rules_have_required_fields(self) -> None:
        """Test that all rules have env_key and config_path."""
        for rule in OVERRIDE_RULES:
            assert rule.env_key
            assert rule.config_path
            assert callable(rule.converter)

    def test_no_duplicate_env_keys(self) -> None:
        """Test that env keys are unique."""
        env_keys = [rule.env_key for rule in OVERRIDE_RULES]
        assert len(env_keys) == len(set(env_keys))
