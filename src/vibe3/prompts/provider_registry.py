"""Provider registry for prompt variable resolution."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from vibe3.prompts.exceptions import ProviderNotFoundError

ProviderCallable = Callable[[dict[str, Any]], str]


class ProviderRegistry:
    """Registry mapping provider names to callable resolvers.

    Providers receive the full runtime context and return a string value.
    """

    def __init__(self) -> None:
        self._providers: dict[str, ProviderCallable] = {}

    def register(self, name: str, provider: ProviderCallable) -> None:
        """Register or overwrite a named provider."""
        self._providers[name] = provider

    def call(self, name: str, context: dict[str, Any]) -> str:
        """Invoke a registered provider with the given context."""
        if name not in self._providers:
            raise ProviderNotFoundError(name)
        return self._providers[name](context)

    def list_providers(self) -> list[str]:
        """Return sorted list of registered provider names."""
        return sorted(self._providers)
