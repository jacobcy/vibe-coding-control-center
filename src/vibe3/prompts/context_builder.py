"""Callable context builder backed by PromptAssembler.

Provides a unified callable interface that:
- Resolves variables via PromptAssembler
- Captures the last PromptRenderResult for dry-run provenance logging
- Satisfies the Callable[[], str] contract expected by CodeagentCommand
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from vibe3.prompts.assembler import PromptAssembler
from vibe3.prompts.models import (
    PromptRecipe,
    PromptRenderResult,
    PromptVariableSource,
    VariableSourceKind,
)
from vibe3.prompts.provider_registry import ProviderRegistry


class PromptContextBuilder:
    """Callable context builder backed by PromptAssembler.

    Usage::

        cb = PromptContextBuilder(assembler, recipe)
        text = cb()               # renders via assembler
        prov = cb.last_result     # access provenance after call

    Satisfies ``Callable[[], str]`` for CodeagentCommand.context_builder.
    """

    def __init__(
        self,
        assembler: PromptAssembler,
        recipe: PromptRecipe,
        runtime_context: dict | None = None,
    ) -> None:
        self._assembler = assembler
        self._recipe = recipe
        self._runtime_context: dict = runtime_context or {}
        self.last_result: PromptRenderResult | None = None

    def __call__(self) -> str:
        self.last_result = self._assembler.render(self._recipe, self._runtime_context)
        return self.last_result.rendered_text


def make_context_builder(
    template_key: str,
    body_provider_key: str,
    body_fn: Callable[[], str],
    prompts_path: Path | None = None,
) -> PromptContextBuilder:
    """Create a PromptContextBuilder for a single-variable body recipe.

    Args:
        template_key: Dotted key in prompts.yaml, e.g. ``"run.plan"``.
        body_provider_key: Provider registry key, e.g. ``"run.context"``.
        body_fn: Zero-arg callable returning the assembled prompt body string.
        prompts_path: Optional override for prompts.yaml path.

    Returns:
        PromptContextBuilder ready to be used as CodeagentCommand.context_builder.
    """
    prefix = body_provider_key.split(".")[0]  # "run", "plan", "review"
    variable_name = f"{prefix}_prompt_body"

    recipe = PromptRecipe(
        template_key=template_key,
        variables={
            variable_name: PromptVariableSource(
                kind=VariableSourceKind.PROVIDER,
                provider=body_provider_key,
            )
        },
    )
    registry = ProviderRegistry()

    def provider(_: Any) -> str:
        return body_fn()

    registry.register(body_provider_key, provider)
    assembler = PromptAssembler(prompts_path=prompts_path, registry=registry)
    return PromptContextBuilder(assembler, recipe)
