"""Builtin variable source resolvers for the prompt assembly layer."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from loguru import logger

from vibe3.clients import resolve_runtime_asset
from vibe3.prompts.exceptions import ProviderNotFoundError
from vibe3.prompts.models import PromptVariableSource, VariableSourceKind
from vibe3.prompts.provider_registry import ProviderRegistry


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
    from vibe3.clients import find_repo_root

    try:
        repo_root = find_repo_root()
        abs_path = repo_root / skill_path
    except Exception:
        # Fallback to cwd-relative if not in git repo
        abs_path = Path(skill_path)
    try:
        return abs_path.read_text(encoding="utf-8")
    except OSError:
        return None


def _resolve_literal(src: PromptVariableSource) -> str:
    return src.value or ""


def _resolve_file(
    src: PromptVariableSource,
    warnings: list[str] | None = None,
) -> str:
    """Resolve file source with optional project-specific overlay.

    For governance materials (supervisor/governance/*.md), automatically
    appends project-specific content from .vibe/governance/*.md if present.

    Args:
        src: Variable source with file path
        warnings: Optional list to collect warning messages

    Returns:
        File content (base + project overlay if applicable), or empty string on error

    Example:
        supervisor/governance/roadmap-intake.md
        + .vibe/governance/roadmap-intake.md (if exists)
        = Combined content for governance material
    """
    if not src.path:
        return ""

    # Read base file
    path = resolve_runtime_asset(src.path)
    if not path.exists():
        msg = f"File source not found: {src.path}"
        logger.bind(domain="prompt_assembly").warning(msg)
        if warnings is not None:
            warnings.append(msg)
        return ""

    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        msg = f"Cannot read file source {src.path}: {exc}"
        logger.bind(domain="prompt_assembly").warning(msg)
        if warnings is not None:
            warnings.append(msg)
        return ""

    # Auto-append project-specific overlay for governance materials
    if src.path.startswith("supervisor/governance/") and src.path.endswith(".md"):
        basename = Path(src.path).name
        project_overlay_path = f".vibe/governance/{basename}"
        project_path = resolve_runtime_asset(project_overlay_path)

        if project_path.exists():
            try:
                project_content = project_path.read_text(encoding="utf-8")
                content = content + "\n\n" + project_content
                logger.bind(domain="prompt_assembly").info(
                    f"Appended project-specific overlay: {project_overlay_path}"
                )
            except OSError as exc:
                logger.bind(domain="prompt_assembly").warning(
                    f"Cannot read project overlay {project_overlay_path}: {exc}"
                )

    return content


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
    warnings: list[str] | None = None,
) -> str:
    """Resolve a single variable source to its string value."""
    if src.kind == VariableSourceKind.LITERAL:
        return _resolve_literal(src)
    if src.kind == VariableSourceKind.FILE:
        return _resolve_file(src, warnings=warnings)
    if src.kind == VariableSourceKind.SKILL:
        return _resolve_skill(src, skill_path_resolver)
    if src.kind == VariableSourceKind.COMMAND:
        return _resolve_command(src)
    if src.kind == VariableSourceKind.PROVIDER:
        return _resolve_provider(src, runtime_context, registry)
    return ""
