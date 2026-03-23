"""AI client using litellm for multi-provider support."""

import importlib.util
import os
from typing import Any

from loguru import logger

from vibe3.config.settings import AIConfig

# Check if litellm is available without importing
HAS_LITELLM = importlib.util.find_spec("litellm") is not None


class AIClient:
    """Client for AI text generation using litellm.

    Supports 100+ models: DeepSeek, OpenAI, Anthropic, Ollama, etc.
    Designed for graceful degradation - never throws, returns None on failure.
    """

    def __init__(self, config: AIConfig) -> None:
        """Initialize AI client.

        Args:
            config: AI configuration
        """
        self.config = config
        self._api_key: str | None = None
        self._base_url: str | None = None

        if not config.enabled:
            logger.bind(module="ai_client").debug("AI assistance disabled in config")
            return

        if not HAS_LITELLM:
            logger.bind(module="ai_client").warning(
                "litellm package not installed, AI features disabled"
            )
            return

        api_key = os.environ.get(config.api_key_env)
        if not api_key:
            logger.bind(module="ai_client").debug(
                f"API key not found in environment: {config.api_key_env}"
            )
            return

        self._api_key = api_key
        self._base_url = config.base_url
        logger.bind(module="ai_client").debug(
            f"AI client initialized: model={config.model}"
        )

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs: Any,
    ) -> str | None:
        """Generate text using AI.

        Args:
            system_prompt: System prompt
            user_prompt: User prompt
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            Generated text or None on failure
        """
        if self._api_key is None:
            return None

        try:
            import litellm

            # Set API key and base URL for litellm
            litellm.api_key = self._api_key
            if self._base_url:
                litellm.api_base = self._base_url

            response = litellm.completion(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                timeout=self.config.timeout,
                **kwargs,
            )

            content = response.choices[0].message.content
            if content is None:
                logger.bind(module="ai_client").warning("AI returned empty content")
                return None

            return str(content)

        except Exception as e:
            logger.bind(module="ai_client").warning(f"AI API call failed: {e}")
            return None
