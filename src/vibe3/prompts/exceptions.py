"""Exceptions for the prompt assembly layer.

All exceptions inherit from VibeError so that the CLI layer's unified
``except VibeError`` handler catches prompt assembly failures correctly.
"""

from __future__ import annotations

from vibe3.exceptions import VibeError


class PromptAssemblyError(VibeError):
    """Base class for prompt assembly errors (non-recoverable by default)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, recoverable=False)


class MissingVariableError(PromptAssemblyError):
    """Raised when a template variable has no declared source."""

    def __init__(self, variable: str, template_key: str) -> None:
        self.variable = variable
        self.template_key = template_key
        super().__init__(
            f"Template '{template_key}' requires variable '{variable}' "
            "but no source was declared in the recipe."
        )


class UnusedVariableError(PromptAssemblyError):
    """Raised when a declared recipe variable is not referenced in the template."""

    def __init__(self, variable: str, template_key: str) -> None:
        self.variable = variable
        self.template_key = template_key
        super().__init__(
            f"Recipe for '{template_key}' declares variable '{variable}' "
            "but the template never references it."
        )


class TemplateNotFoundError(PromptAssemblyError):
    """Raised when a template key cannot be resolved."""

    def __init__(self, template_key: str) -> None:
        self.template_key = template_key
        super().__init__(f"Prompt template not found: '{template_key}'")


class ProviderNotFoundError(PromptAssemblyError):
    """Raised when a named provider is not registered."""

    def __init__(self, provider: str) -> None:
        self.provider = provider
        super().__init__(f"Prompt provider not registered: '{provider}'")
