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

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vibe3.prompts.assembler import PromptAssembler
    from vibe3.prompts.context_builder import (
        PromptContextBuilder,
        make_context_builder,
    )
    from vibe3.prompts.exceptions import (
        MissingVariableError,
        PromptAssemblyError,
        ProviderNotFoundError,
        TemplateNotFoundError,
        UnusedVariableError,
    )
    from vibe3.prompts.manifest import (
        PromptManifest,
        PromptProvider,
        PromptRecipeDefinition,
        PromptRecipeVariant,
    )
    from vibe3.prompts.models import (
        LoadedPromptRecipeDefinition,
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
        resolve_prompt_template,
    )
    from vibe3.prompts.validation import (
        PromptValidationResult,
        PromptValidationService,
        ValidationIssue,
    )


def __getattr__(name: str) -> Any:
    """Lazy import for all symbols to avoid cross-module side effects."""
    if name == "PromptAssembler":
        from vibe3.prompts.assembler import PromptAssembler

        return PromptAssembler
    if name == "PromptContextBuilder":
        from vibe3.prompts.context_builder import PromptContextBuilder

        return PromptContextBuilder
    if name == "make_context_builder":
        from vibe3.prompts.context_builder import make_context_builder

        return make_context_builder
    if name == "PromptManifest":
        from vibe3.prompts.manifest import PromptManifest

        return PromptManifest
    if name == "PromptProvider":
        from vibe3.prompts.manifest import PromptProvider

        return PromptProvider
    if name == "PromptRecipeDefinition":
        from vibe3.prompts.manifest import PromptRecipeDefinition

        return PromptRecipeDefinition
    if name == "PromptRecipeVariant":
        from vibe3.prompts.manifest import PromptRecipeVariant

        return PromptRecipeVariant
    if name == "LoadedPromptRecipeDefinition":
        from vibe3.prompts.models import LoadedPromptRecipeDefinition

        return LoadedPromptRecipeDefinition
    if name == "PromptMaterialSpec":
        from vibe3.prompts.models import PromptMaterialSpec

        return PromptMaterialSpec
    if name == "PromptRecipe":
        from vibe3.prompts.models import PromptRecipe

        return PromptRecipe
    if name == "PromptRecipeKind":
        from vibe3.prompts.models import PromptRecipeKind

        return PromptRecipeKind
    if name == "PromptRecipeVariantSpec":
        from vibe3.prompts.models import PromptRecipeVariantSpec

        return PromptRecipeVariantSpec
    if name == "PromptRenderResult":
        from vibe3.prompts.models import PromptRenderResult

        return PromptRenderResult
    if name == "PromptSectionSpec":
        from vibe3.prompts.models import PromptSectionSpec

        return PromptSectionSpec
    if name == "PromptVariableProvenance":
        from vibe3.prompts.models import PromptVariableProvenance

        return PromptVariableProvenance
    if name == "PromptVariableSource":
        from vibe3.prompts.models import PromptVariableSource

        return PromptVariableSource
    if name == "VariableSourceKind":
        from vibe3.prompts.models import VariableSourceKind

        return VariableSourceKind
    if name == "ProviderRegistry":
        from vibe3.prompts.provider_registry import ProviderRegistry

        return ProviderRegistry
    if name == "MissingVariableError":
        from vibe3.prompts.exceptions import MissingVariableError

        return MissingVariableError
    if name == "PromptAssemblyError":
        from vibe3.prompts.exceptions import PromptAssemblyError

        return PromptAssemblyError
    if name == "ProviderNotFoundError":
        from vibe3.prompts.exceptions import ProviderNotFoundError

        return ProviderNotFoundError
    if name == "TemplateNotFoundError":
        from vibe3.prompts.exceptions import TemplateNotFoundError

        return TemplateNotFoundError
    if name == "UnusedVariableError":
        from vibe3.prompts.exceptions import UnusedVariableError

        return UnusedVariableError
    if name == "PromptValidationResult":
        from vibe3.prompts.validation import PromptValidationResult

        return PromptValidationResult
    if name == "PromptValidationService":
        from vibe3.prompts.validation import PromptValidationService

        return PromptValidationService
    if name == "ValidationIssue":
        from vibe3.prompts.validation import ValidationIssue

        return ValidationIssue
    if name == "DEFAULT_PROMPTS_PATH":
        from vibe3.prompts.template_loader import DEFAULT_PROMPTS_PATH

        return DEFAULT_PROMPTS_PATH
    if name == "resolve_prompt_template":
        from vibe3.prompts.template_loader import resolve_prompt_template

        return resolve_prompt_template
    if name == "build_tools_guide_section":
        from vibe3.prompts.sections import build_tools_guide_section

        return build_tools_guide_section
    if name == "resolve_common_rules_path":
        from vibe3.prompts.sections import resolve_common_rules_path

        return resolve_common_rules_path

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
    "UnusedVariableError",
    # Validation
    "PromptValidationResult",
    "PromptValidationService",
    "ValidationIssue",
    # Template helpers
    "DEFAULT_PROMPTS_PATH",
    "resolve_prompt_template",
    # Section builders
    "build_tools_guide_section",
    "resolve_common_rules_path",
]
