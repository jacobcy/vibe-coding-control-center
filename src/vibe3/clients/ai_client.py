"""AI client for OpenAI-compatible API calls."""

import os
from typing import Any

from loguru import logger

from vibe3.config.settings import AIConfig


class AIClient:
    """Client for AI text generation.

    Supports OpenAI-compatible APIs (OpenAI, Ollama, vLLM, etc.).
    Designed for graceful degradation - never throws, returns None on failure.
    """

    def __init__(self, config: AIConfig) -> None:
        """Initialize AI client.

        Args:
            config: AI configuration
        """
        self.config = config
        self._client: Any = None

        if not config.enabled:
            logger.bind(module="ai_client").debug("AI assistance disabled in config")
            return

        api_key = os.environ.get(config.api_key_env)
        if not api_key:
            logger.bind(module="ai_client").debug(
                f"API key not found in environment: {config.api_key_env}"
            )
            return

        try:
            from openai import OpenAI

            kwargs: dict[str, Any] = {
                "api_key": api_key,
                "timeout": config.timeout,
            }
            if config.base_url:
                kwargs["base_url"] = config.base_url

            self._client = OpenAI(**kwargs)
            logger.bind(module="ai_client").debug(
                f"AI client initialized: provider={config.provider}, "
                f"model={config.model}"
            )
        except ImportError:
            logger.bind(module="ai_client").warning(
                "openai package not installed, AI features disabled"
            )
        except Exception as e:
            logger.bind(module="ai_client").warning(
                f"Failed to initialize AI client: {e}"
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
        if self._client is None:
            return None

        try:
            response = self._client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                **kwargs,
            )

            content = response.choices[0].message.content
            if content is None:
                logger.bind(module="ai_client").warning("AI returned empty content")
                return None

            return str(content)

        except TimeoutError:
            logger.bind(module="ai_client").warning(
                f"AI API call timed out after {self.config.timeout}s"
            )
            return None
        except Exception as e:
            logger.bind(module="ai_client").warning(f"AI API call failed: {e}")
            return None
