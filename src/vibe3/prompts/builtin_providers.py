"""Builtin variable source resolvers for the prompt assembly layer."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from loguru import logger

from vibe3.prompts.exceptions import ProviderNotFoundError
from vibe3.prompts.models import PromptVariableSource, VariableSourceKind
from vibe3.prompts.provider_registry import ProviderRegistry
from vibe3.resources.runtime_assets import resolve_runtime_asset


def resolve_skill_content(
    skill_name: str,
    skill_path_resolver: Callable[[str], str | None] | None = None,
) -> str | None:
    """Resolve skill SKILL.md content through profile.

    Args:
        skill_name: Skill name
        skill_path_resolver: Optional callable to resolve skill name to path.
            If None, returns None (cannot resolve skill).

    Returns:
        Skill content or None if not found
    """
    if skill_path_resolver is None:
        return None

    skill_path = skill_path_resolver(skill_name)
    if skill_path is None:
        return None

    # Resolve relative path against repo root for CWD-independent access
    from vibe3.clients import GitClient

    try:
        git_client = GitClient()
        git_common_dir = git_client.get_git_common_dir()
        if git_common_dir:
            repo_root = Path(git_common_dir).parent
            abs_path = repo_root / skill_path
        else:
            # Fallback to cwd-relative if not in git repo
            abs_path = Path(skill_path)
        return abs_path.read_text(encoding="utf-8")
    except OSError:
        return None


def _resolve_literal(src: PromptVariableSource) -> str:
    return src.value or ""


def _resolve_file(src: PromptVariableSource) -> str:
    if not src.path:
        return ""
    path = resolve_runtime_asset(src.path)
    if not path.exists():
        logger.bind(domain="prompt_assembly").warning(
            f"File source not found: {src.path}"
        )
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.bind(domain="prompt_assembly").warning(
            f"Cannot read file source {src.path}: {exc}"
        )
        return ""


def _resolve_skill(
    src: PromptVariableSource,
    skill_path_resolver: Callable[[str], str | None] | None = None,
) -> str:
    if not src.skill:
        return ""
    skill_content = resolve_skill_content(src.skill, skill_path_resolver)
    if skill_content is None:
        logger.bind(domain="prompt_assembly").warning(f"Skill not found: {src.skill}")
        return ""
    return skill_content


def _resolve_command(src: PromptVariableSource) -> str:
    if not src.command:
        return ""
    try:
        result = subprocess.run(
            src.command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            logger.bind(domain="prompt_assembly").warning(
                f"Command source exited {result.returncode}: {src.command}"
            )
            return ""
        return result.stdout
    except Exception as exc:
        logger.bind(domain="prompt_assembly").warning(
            f"Command source failed ({src.command}): {exc}"
        )
        return ""


def _resolve_provider(
    src: PromptVariableSource,
    runtime_context: dict[str, Any],
    registry: ProviderRegistry,
) -> str:
    if not src.provider:
        return ""
    try:
        return registry.call(src.provider, runtime_context)
    except ProviderNotFoundError:
        logger.bind(domain="prompt_assembly").warning(
            f"Provider not found: {src.provider}"
        )
        return ""


def resolve_source(
    src: PromptVariableSource,
    runtime_context: dict[str, Any],
    registry: ProviderRegistry,
    skill_path_resolver: Callable[[str], str | None] | None = None,
) -> str:
    """Resolve a single variable source to its string value."""
    if src.kind == VariableSourceKind.LITERAL:
        return _resolve_literal(src)
    if src.kind == VariableSourceKind.FILE:
        return _resolve_file(src)
    if src.kind == VariableSourceKind.SKILL:
        return _resolve_skill(src, skill_path_resolver)
    if src.kind == VariableSourceKind.COMMAND:
        return _resolve_command(src)
    if src.kind == VariableSourceKind.PROVIDER:
        return _resolve_provider(src, runtime_context, registry)
    return ""
