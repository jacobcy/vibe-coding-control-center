"""Tests for AI client."""

import os
from unittest.mock import MagicMock, patch

from vibe3.clients.ai_client import AIClient
from vibe3.config.settings import AIConfig


class TestAIClient:
    """Tests for AIClient class."""

    def test_init_with_valid_config(self) -> None:
        """Test initialization with valid config."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            config = AIConfig(enabled=True, provider="openai", model="gpt-4o-mini")
            client = AIClient(config)
            assert client.config == config

    def test_init_with_missing_api_key(self) -> None:
        """Test initialization with missing API key returns None."""
        with patch.dict(os.environ, {}, clear=True):
            config = AIConfig(enabled=True, provider="openai", model="gpt-4o-mini")
            client = AIClient(config)
            assert client._client is None

    def test_init_disabled_returns_none(self) -> None:
        """Test initialization when disabled."""
        config = AIConfig(enabled=False, provider="openai", model="gpt-4o-mini")
        client = AIClient(config)
        assert client._client is None

    def test_init_with_custom_base_url(self) -> None:
        """Test initialization with custom base URL (Ollama/vLLM)."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            config = AIConfig(
                enabled=True,
                provider="openai",
                model="llama3",
                base_url="http://localhost:11434/v1",
            )
            with patch("openai.OpenAI") as mock_openai:
                mock_client = MagicMock()
                mock_openai.return_value = mock_client
                AIClient(config)
                mock_openai.assert_called_once()
                call_kwargs = mock_openai.call_args[1]
                assert call_kwargs["base_url"] == "http://localhost:11434/v1"
                assert call_kwargs["api_key"] == "test-key"

    def test_generate_text_success(self) -> None:
        """Test successful text generation."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            config = AIConfig(enabled=True, provider="openai", model="gpt-4o-mini")
            with patch("openai.OpenAI") as mock_openai:
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = "generated text"
                mock_client.chat.completions.create.return_value = mock_response
                mock_openai.return_value = mock_client

                client = AIClient(config)
                result = client.generate_text("system prompt", "user prompt")

                assert result == "generated text"
                mock_client.chat.completions.create.assert_called_once_with(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "system prompt"},
                        {"role": "user", "content": "user prompt"},
                    ],
                )

    def test_generate_text_disabled_returns_none(self) -> None:
        """Test generation when disabled returns None."""
        config = AIConfig(enabled=False, provider="openai", model="gpt-4o-mini")
        client = AIClient(config)
        result = client.generate_text("system prompt", "user prompt")
        assert result is None

    def test_generate_text_no_client_returns_none(self) -> None:
        """Test generation with no client returns None."""
        with patch.dict(os.environ, {}, clear=True):
            config = AIConfig(enabled=True, provider="openai", model="gpt-4o-mini")
            client = AIClient(config)
            result = client.generate_text("system prompt", "user prompt")
            assert result is None

    def test_generate_text_api_error_returns_none(self) -> None:
        """Test generation with API error returns None."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            config = AIConfig(enabled=True, provider="openai", model="gpt-4o-mini")
            with patch("openai.OpenAI") as mock_openai:
                mock_client = MagicMock()
                mock_client.chat.completions.create.side_effect = Exception("API error")
                mock_openai.return_value = mock_client

                client = AIClient(config)
                result = client.generate_text("system prompt", "user prompt")

                assert result is None

    def test_generate_text_timeout_returns_none(self) -> None:
        """Test generation with timeout returns None."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            config = AIConfig(enabled=True, provider="openai", model="gpt-4o-mini")
            with patch("openai.OpenAI") as mock_openai:
                mock_client = MagicMock()
                mock_client.chat.completions.create.side_effect = TimeoutError(
                    "timeout"
                )
                mock_openai.return_value = mock_client

                client = AIClient(config)
                result = client.generate_text("system prompt", "user prompt")

                assert result is None

    def test_generate_text_empty_content_returns_none(self) -> None:
        """Test generation with empty content returns None."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            config = AIConfig(enabled=True, provider="openai", model="gpt-4o-mini")
            with patch("openai.OpenAI") as mock_openai:
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = None
                mock_client.chat.completions.create.return_value = mock_response
                mock_openai.return_value = mock_client

                client = AIClient(config)
                result = client.generate_text("system prompt", "user prompt")

                assert result is None

    def test_generate_text_with_extra_params(self) -> None:
        """Test generation with extra parameters."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            config = AIConfig(enabled=True, provider="openai", model="gpt-4o-mini")
            with patch("openai.OpenAI") as mock_openai:
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = "result"
                mock_client.chat.completions.create.return_value = mock_response
                mock_openai.return_value = mock_client

                client = AIClient(config)
                result = client.generate_text(
                    "system prompt", "user prompt", temperature=0.7, max_tokens=100
                )

                assert result == "result"
                mock_client.chat.completions.create.assert_called_once_with(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "system prompt"},
                        {"role": "user", "content": "user prompt"},
                    ],
                    temperature=0.7,
                    max_tokens=100,
                )

    def test_uses_environment_key_name_from_config(self) -> None:
        """Test that client uses the environment variable name from config."""
        with patch.dict(os.environ, {"CUSTOM_API_KEY": "custom-key"}, clear=True):
            config = AIConfig(
                enabled=True,
                provider="openai",
                model="gpt-4o-mini",
                api_key_env="CUSTOM_API_KEY",
            )
            with patch("openai.OpenAI") as mock_openai:
                mock_client = MagicMock()
                mock_openai.return_value = mock_client

                AIClient(config)

                mock_openai.assert_called_once()
                call_kwargs = mock_openai.call_args[1]
                assert call_kwargs["api_key"] == "custom-key"
