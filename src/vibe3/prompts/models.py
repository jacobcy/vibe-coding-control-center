"""Data models for prompt recipes and render provenance."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class VariableSourceKind(str, Enum):
    """Supported variable source kinds."""

    LITERAL = "literal"
    SKILL = "skill"
    FILE = "file"
    COMMAND = "command"
    PROVIDER = "provider"


class PromptVariableSource(BaseModel):
    """Declares where a template variable value comes from."""

    model_config = {"frozen": True}

    kind: VariableSourceKind
    # kind=literal
    value: str | None = None
    # kind=skill
    skill: str | None = None
    # kind=file
    path: str | None = None
    # kind=command
    command: str | None = None
    # kind=provider
    provider: str | None = None
    # optional runtime context key override for provider calls
    context_key: str | None = None
    # extra kwargs forwarded to provider
    kwargs: dict[str, Any] = Field(default_factory=dict)


class PromptRecipe(BaseModel):
    """Describes how to assemble a prompt: template key + variable sources."""

    model_config = {"frozen": True}

    template_key: str
    variables: dict[str, PromptVariableSource] = Field(default_factory=dict)
    # optional description shown in dry-run output
    description: str | None = None


class PromptVariableProvenance(BaseModel):
    """Records where a resolved variable value came from."""

    model_config = {"frozen": True}

    variable: str
    source_kind: VariableSourceKind
    resolved_from: str
    value_preview: str = ""


class PromptRenderResult(BaseModel):
    """Result of rendering a prompt recipe."""

    model_config = {"frozen": True}

    recipe_key: str
    template_source: str
    rendered_text: str
    provenance: tuple[PromptVariableProvenance, ...] = ()
