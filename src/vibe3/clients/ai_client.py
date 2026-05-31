"""AI client using litellm for multi-provider support."""

import importlib.util
from typing import Any

from loguru import logger

# Check if litellm is available without importing
HAS_LITELLM = importlib.util.find_spec("litellm") is not None


class AIClient:
    """Client for AI text generation using litellm.

    Supports 100+ models: DeepSeek, OpenAI, Anthropic, Ollama, etc.
    Designed for graceful degradation - never throws, returns None on failure.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: int = 30,
        base_url: str | None = None,
    ) -> None:
        """Initialize AI client.

        Args:
            api_key: API key for the AI service
            model: Model name (e.g., "deepseek/deepseek-chat")
            timeout: Request timeout in seconds
            base_url: Optional custom base URL for the API
        """
        self.model = model
        self.timeout = timeout
        self._base_url: str | None = base_url

        if not HAS_LITELLM:
            logger.bind(module="ai_client").warning(
                "litellm package not installed, AI features disabled"
            )
            self._api_key = None
            return

        if not api_key:
            logger.bind(module="ai_client").debug("API key not provided")
            self._api_key = None
            return

        self._api_key = api_key
        logger.bind(module="ai_client").debug(f"AI client initialized: model={model}")

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
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                timeout=self.timeout,
                **kwargs,
            )

            content = response.choices[0].message.content  # type: ignore[union-attr]
            if content is None:
                logger.bind(module="ai_client").warning("AI returned empty content")
                return None

            return str(content)

        except Exception as e:
            logger.bind(module="ai_client").warning(f"AI API call failed: {e}")
            return None
