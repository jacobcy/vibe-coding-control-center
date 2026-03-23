"""Tests for AI client."""

import os
from unittest.mock import MagicMock, patch

import pytest

from vibe3.clients.ai_client import HAS_LITELLM, AIClient
from vibe3.config.settings import AIConfig


@pytest.mark.skipif(not HAS_LITELLM, reason="litellm not installed")
class TestAIClient:
    """Tests for AIClient class."""

    def test_init_with_valid_config(self) -> None:
        """Test initialization with valid config."""
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            config = AIConfig(enabled=True, model="deepseek/deepseek-chat")
            client = AIClient(config)
            assert client.config == config
            assert client._api_key == "test-key"

    def test_init_with_missing_api_key(self) -> None:
        """Test initialization with missing API key returns None."""
        with patch.dict(os.environ, {}, clear=True):
            config = AIConfig(enabled=True, model="deepseek/deepseek-chat")
            client = AIClient(config)
            assert client._api_key is None

    def test_init_disabled_returns_none(self) -> None:
        """Test initialization when disabled."""
        config = AIConfig(enabled=False, model="deepseek-chat")
        client = AIClient(config)
        assert client._api_key is None

    def test_init_with_custom_base_url(self) -> None:
        """Test initialization with custom base URL."""
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            config = AIConfig(
                enabled=True,
                base_url="http://localhost:11434/v1",
                model="ollama/llama3",
            )
            client = AIClient(config)
            assert client._base_url == "http://localhost:11434/v1"

    def test_generate_text_success(self) -> None:
        """Test successful text generation."""
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            config = AIConfig(enabled=True, model="deepseek/deepseek-chat")
            with patch("litellm.completion") as mock_completion:
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = "generated text"
                mock_completion.return_value = mock_response

                client = AIClient(config)
                result = client.generate_text("system prompt", "user prompt")

                assert result == "generated text"
                mock_completion.assert_called_once()

    def test_generate_text_disabled_returns_none(self) -> None:
        """Test generation when disabled returns None."""
        config = AIConfig(enabled=False, model="deepseek-chat")
        client = AIClient(config)
        result = client.generate_text("system prompt", "user prompt")
        assert result is None

    def test_generate_text_no_api_key_returns_none(self) -> None:
        """Test generation with no API key returns None."""
        with patch.dict(os.environ, {}, clear=True):
            config = AIConfig(enabled=True, model="deepseek/deepseek-chat")
            client = AIClient(config)
            result = client.generate_text("system prompt", "user prompt")
            assert result is None

    def test_generate_text_api_error_returns_none(self) -> None:
        """Test generation with API error returns None."""
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            config = AIConfig(enabled=True, model="deepseek/deepseek-chat")
            with patch("litellm.completion") as mock_completion:
                mock_completion.side_effect = Exception("API error")

                client = AIClient(config)
                result = client.generate_text("system prompt", "user prompt")

                assert result is None

    def test_generate_text_empty_content_returns_none(self) -> None:
        """Test generation with empty content returns None."""
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            config = AIConfig(enabled=True, model="deepseek/deepseek-chat")
            with patch("litellm.completion") as mock_completion:
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = None
                mock_completion.return_value = mock_response

                client = AIClient(config)
                result = client.generate_text("system prompt", "user prompt")

                assert result is None

    def test_generate_text_with_extra_params(self) -> None:
        """Test generation with extra parameters."""
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            config = AIConfig(enabled=True, model="deepseek/deepseek-chat")
            with patch("litellm.completion") as mock_completion:
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = "result"
                mock_completion.return_value = mock_response

                client = AIClient(config)
                result = client.generate_text(
                    "system prompt", "user prompt", temperature=0.7, max_tokens=100
                )

                assert result == "result"
                call_kwargs = mock_completion.call_args[1]
                assert "temperature" in call_kwargs
                assert "max_tokens" in call_kwargs

    def test_uses_environment_key_name_from_config(self) -> None:
        """Test that client uses the environment variable name from config."""
        with patch.dict(os.environ, {"CUSTOM_API_KEY": "custom-key"}, clear=True):
            config = AIConfig(
                enabled=True,
                api_key_env="CUSTOM_API_KEY",
                model="deepseek-chat",
            )
            client = AIClient(config)
            assert client._api_key == "custom-key"


class TestAIClientWithoutLitellm:
    """Tests for AIClient when litellm is not installed."""

    def test_init_without_litellm(self) -> None:
        """Test initialization when litellm is not installed."""
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            with patch("vibe3.clients.ai_client.HAS_LITELLM", False):
                config = AIConfig(enabled=True, model="deepseek/deepseek-chat")
                client = AIClient(config)
                assert client._api_key is None

    def test_generate_text_without_litellm_returns_none(self) -> None:
        """Test generation when litellm is not installed."""
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            with patch("vibe3.clients.ai_client.HAS_LITELLM", False):
                config = AIConfig(enabled=True, model="deepseek/deepseek-chat")
                client = AIClient(config)
                result = client.generate_text("system prompt", "user prompt")
                assert result is None
