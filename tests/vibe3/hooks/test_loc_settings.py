"""Tests for LOC settings parsing and runtime config alignment."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from vibe3.config.settings import VibeConfig


def _load_loc_settings_module():
    module_path = Path("scripts/hooks/loc_settings.py")
    spec = importlib.util.spec_from_file_location("loc_settings", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError("Failed to load loc_settings module")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("loc_settings", module)
    spec.loader.exec_module(module)
    return module


def test_loc_settings_parser_reads_unified_exceptions() -> None:
    module = _load_loc_settings_module()
    settings = module.load_loc_settings()
    shell_files = module.iter_files(settings.code_paths_v2_shell, suffixes=(".sh",))

    assert settings.code_paths_v3_python == ("src/vibe3/",)
    assert len(settings.exceptions) == len(
        {entry.path for entry in settings.exceptions}
    )
    assert Path("lib/alias/worktree.sh") in shell_files
    assert (
        module.find_exception(
            settings.exceptions,
            "src/vibe3/clients/git_client.py",
        )
        is not None
    )
    assert (
        module.find_exception(
            settings.exceptions,
            "src/vibe3/roles/review.py",
        )
        is not None
    )


def test_runtime_config_loads_same_loc_exceptions() -> None:
    module = _load_loc_settings_module()
    settings = module.load_loc_settings()
    config = VibeConfig.from_yaml(Path("config/v3/settings.yaml"))
    exceptions = {
        entry.path: entry for entry in config.code_limits.single_file_loc.exceptions
    }
    hook_exception = module.find_exception(
        settings.exceptions,
        "src/vibe3/services/check_service.py",
    )

    assert hook_exception is not None
    # Verify both configs have the same limit (sync check)
    expected_path = "src/vibe3/services/check_service.py"
    assert hook_exception.limit == exceptions[expected_path].limit
    # Verify the limit is reasonable (updated from 600 to 620 after refactoring)
    assert hook_exception.limit == 620
    assert exceptions["src/vibe3/roles/review.py"].reason != ""


def test_runtime_defaults_align_with_hook_fallbacks() -> None:
    config = VibeConfig()

    assert config.code_limits.single_file_loc.default == 300
    assert config.code_limits.single_file_loc.max == 400
    assert config.code_limits.total_file_loc.v2_shell == 4000
    assert config.code_limits.total_file_loc.v3_python == 32000
