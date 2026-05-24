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
"""

from vibe3.prompts.assembler import PromptAssembler
from vibe3.prompts.context_builder import PromptContextBuilder, make_context_builder
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
from vibe3.prompts.template_loader import (
    DEFAULT_PROMPTS_PATH,
    resolve_prompt_template,
)
from vibe3.prompts.validation import (
    PromptValidationResult,
    PromptValidationService,
    ValidationIssue,
)

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
]
