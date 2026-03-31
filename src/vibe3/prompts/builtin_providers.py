"""Builtin variable source resolvers for the prompt assembly layer."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from loguru import logger

from vibe3.prompts.exceptions import ProviderNotFoundError
from vibe3.prompts.models import PromptVariableSource, VariableSourceKind
from vibe3.prompts.provider_registry import ProviderRegistry
from vibe3.services.run_usecase import RunUsecase


def find_skill_file(skill_name: str) -> Path | None:
    """Delegate to RunUsecase.find_skill_file for skill lookup."""
    return RunUsecase.find_skill_file(skill_name)


def _resolve_literal(src: PromptVariableSource) -> str:
    return src.value or ""


def _resolve_file(src: PromptVariableSource) -> str:
    if not src.path:
        return ""
    path = Path(src.path)
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


def _resolve_skill(src: PromptVariableSource) -> str:
    if not src.skill:
        return ""
    skill_path = find_skill_file(src.skill)
    if skill_path is None:
        logger.bind(domain="prompt_assembly").warning(f"Skill not found: {src.skill}")
        return ""
    try:
        return skill_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.bind(domain="prompt_assembly").warning(
            f"Cannot read skill {src.skill}: {exc}"
        )
        return ""


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
) -> str:
    """Resolve a single variable source to its string value."""
    if src.kind == VariableSourceKind.LITERAL:
        return _resolve_literal(src)
    if src.kind == VariableSourceKind.FILE:
        return _resolve_file(src)
    if src.kind == VariableSourceKind.SKILL:
        return _resolve_skill(src)
    if src.kind == VariableSourceKind.COMMAND:
        return _resolve_command(src)
    if src.kind == VariableSourceKind.PROVIDER:
        return _resolve_provider(src, runtime_context, registry)
    return ""
