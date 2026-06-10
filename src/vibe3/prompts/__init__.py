"""Prompt assembly layer for Vibe3.

Public API:
- PromptAssembler: core prompt rendering engine
- PromptContextBuilder, make_context_builder: callable context builder factory
- PromptManifest: recipe manifest loader
- PromptValidationService: template validation and sample rendering
- Data models: PromptRecipe, PromptRenderResult, PromptVariableSource, etc.
- ProviderRegistry: provider registration and dispatch
- Exceptions: PromptAssemblyError, MissingVariableError, etc.
- Template helpers: DEFAULT_PROMPTS_PATH, resolve_prompt_template
- Section builders: build_tools_guide_section, resolve_common_rules_path
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vibe3.prompts.assembler import PromptAssembler
    from vibe3.prompts.builtin_providers import resolve_source
    from vibe3.prompts.context_builder import (
        PromptContextBuilder,
        make_context_builder,
    )
    from vibe3.prompts.exceptions import (
        MissingVariableError,
        PromptAssemblyError,
        ProviderNotFoundError,
        TemplateNotFoundError,
    )
    from vibe3.prompts.manifest import (
        PromptManifest,
        PromptProvider,
        PromptRecipeDefinition,
        PromptRecipeVariant,
    )
    from vibe3.prompts.models import (
        LoadedPromptRecipeDefinition,
        MaterialEntry,
        PolicyEntry,
        PromptMaterialSpec,
        PromptRecipe,
        PromptRecipeKind,
        PromptRecipeVariantSpec,
        PromptRenderResult,
        PromptSectionSpec,
        PromptVariableProvenance,
        PromptVariableSource,
        VariableSourceKind,
    )
    from vibe3.prompts.provider_registry import ProviderRegistry
    from vibe3.prompts.sections import (
        build_tools_guide_section,
        resolve_common_rules_path,
    )
    from vibe3.prompts.template_loader import (
        DEFAULT_PROMPTS_PATH,
        load_prompt_templates,
        resolve_prompt_template,
        resolve_prompts_path,
    )
    from vibe3.prompts.validation import (
        PromptValidationResult,
        PromptValidationService,
        ValidationIssue,
    )


# Lazy imports
_LAZY_IMPORTS = {
    "PromptAssembler": "vibe3.prompts.assembler",
    "PromptContextBuilder": "vibe3.prompts.context_builder",
    "make_context_builder": "vibe3.prompts.context_builder",
    "MissingVariableError": "vibe3.prompts.exceptions",
    "PromptAssemblyError": "vibe3.prompts.exceptions",
    "ProviderNotFoundError": "vibe3.prompts.exceptions",
    "TemplateNotFoundError": "vibe3.prompts.exceptions",
    "PromptManifest": "vibe3.prompts.manifest",
    "PromptProvider": "vibe3.prompts.manifest",
    "PromptRecipeDefinition": "vibe3.prompts.manifest",
    "PromptRecipeVariant": "vibe3.prompts.manifest",
    "LoadedPromptRecipeDefinition": "vibe3.prompts.models",
    "MaterialEntry": "vibe3.prompts.models",
    "PolicyEntry": "vibe3.prompts.models",
    "PromptMaterialSpec": "vibe3.prompts.models",
    "PromptRecipe": "vibe3.prompts.models",
    "PromptRecipeKind": "vibe3.prompts.models",
    "PromptRecipeVariantSpec": "vibe3.prompts.models",
    "PromptRenderResult": "vibe3.prompts.models",
    "PromptSectionSpec": "vibe3.prompts.models",
    "PromptVariableProvenance": "vibe3.prompts.models",
    "PromptVariableSource": "vibe3.prompts.models",
    "VariableSourceKind": "vibe3.prompts.models",
    "ProviderRegistry": "vibe3.prompts.provider_registry",
    "build_tools_guide_section": "vibe3.prompts.sections",
    "resolve_common_rules_path": "vibe3.prompts.sections",
    "DEFAULT_PROMPTS_PATH": "vibe3.prompts.template_loader",
    "load_prompt_templates": "vibe3.prompts.template_loader",
    "resolve_prompt_template": "vibe3.prompts.template_loader",
    "resolve_prompts_path": "vibe3.prompts.template_loader",
    "resolve_source": "vibe3.prompts.builtin_providers",
    "PromptValidationResult": "vibe3.prompts.validation",
    "PromptValidationService": "vibe3.prompts.validation",
    "ValidationIssue": "vibe3.prompts.validation",
}


def __getattr__(name: str) -> object:
    """Lazy import for prompts symbols to avoid circular dependencies."""
    if name in _LAZY_IMPORTS:
        import importlib

        module = importlib.import_module(_LAZY_IMPORTS[name])
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Core
    "PromptAssembler",
    "PromptContextBuilder",
    "make_context_builder",
    # Manifest
    "PromptManifest",
    "PromptProvider",
    "PromptRecipeDefinition",
    "PromptRecipeVariant",
    # Models
    "LoadedPromptRecipeDefinition",
    "MaterialEntry",
    "PolicyEntry",
    "PromptMaterialSpec",
    "PromptRecipe",
    "PromptRecipeKind",
    "PromptRecipeVariantSpec",
    "PromptRenderResult",
    "PromptSectionSpec",
    "PromptVariableProvenance",
    "PromptVariableSource",
    "VariableSourceKind",
    # Provider
    "ProviderRegistry",
    # Exceptions
    "PromptAssemblyError",
    "MissingVariableError",
    "ProviderNotFoundError",
    "TemplateNotFoundError",
    # Validation
    "PromptValidationResult",
    "PromptValidationService",
    "ValidationIssue",
    # Template helpers
    "DEFAULT_PROMPTS_PATH",
    "load_prompt_templates",
    "resolve_prompt_template",
    "resolve_prompts_path",
    "resolve_source",
    # Section builders
    "build_tools_guide_section",
    "resolve_common_rules_path",
]
