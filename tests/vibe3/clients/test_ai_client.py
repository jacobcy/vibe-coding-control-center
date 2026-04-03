"""Tests for AI client."""

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from vibe3.clients.ai_client import AIClient
from vibe3.config.settings import AIConfig


class TestAIClient:
    """Tests for AIClient class."""

    def _install_fake_litellm(self):
        """Install a fake litellm module for deterministic tests."""
        fake_module = SimpleNamespace(
            completion=MagicMock(), api_key=None, api_base=None
        )
        return patch.dict("sys.modules", {"litellm": fake_module}), fake_module

    def test_init_with_valid_config(self) -> None:
        """Test initialization with valid config."""
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            with patch("vibe3.clients.ai_client.HAS_LITELLM", True):
                config = AIConfig(model="deepseek/deepseek-chat")
                client = AIClient(config)
                assert client.config == config
                assert client._api_key == "test-key"

    def test_init_with_missing_api_key(self) -> None:
        """Test initialization with missing API key returns None."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("vibe3.clients.ai_client.HAS_LITELLM", True):
                config = AIConfig(model="deepseek/deepseek-chat")
                client = AIClient(config)
                assert client._api_key is None

    def test_init_with_custom_base_url(self) -> None:
        """Test initialization with custom base URL."""
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            with patch("vibe3.clients.ai_client.HAS_LITELLM", True):
                config = AIConfig(
                    base_url="http://localhost:11434/v1",
                    model="ollama/llama3",
                )
                client = AIClient(config)
                assert client._base_url == "http://localhost:11434/v1"

    def test_generate_text_success(self) -> None:
        """Test successful text generation."""
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            with patch("vibe3.clients.ai_client.HAS_LITELLM", True):
                patcher, fake_litellm = self._install_fake_litellm()
                with patcher:
                    config = AIConfig(model="deepseek/deepseek-chat")
                    mock_response = MagicMock()
                    mock_response.choices = [MagicMock()]
                    mock_response.choices[0].message.content = "generated text"
                    fake_litellm.completion.return_value = mock_response

                    client = AIClient(config)
                    result = client.generate_text("system prompt", "user prompt")

                    assert result == "generated text"
                    fake_litellm.completion.assert_called_once()
                    assert fake_litellm.api_key == "test-key"

    def test_generate_text_no_api_key_returns_none(self) -> None:
        """Test generation with no API key returns None."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("vibe3.clients.ai_client.HAS_LITELLM", True):
                config = AIConfig(model="deepseek/deepseek-chat")
                client = AIClient(config)
                result = client.generate_text("system prompt", "user prompt")
                assert result is None

    def test_generate_text_api_error_returns_none(self) -> None:
        """Test generation with API error returns None."""
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            with patch("vibe3.clients.ai_client.HAS_LITELLM", True):
                patcher, fake_litellm = self._install_fake_litellm()
                with patcher:
                    config = AIConfig(model="deepseek/deepseek-chat")
                    fake_litellm.completion.side_effect = Exception("API error")

                    client = AIClient(config)
                    result = client.generate_text("system prompt", "user prompt")

                    assert result is None

    def test_generate_text_empty_content_returns_none(self) -> None:
        """Test generation with empty content returns None."""
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            with patch("vibe3.clients.ai_client.HAS_LITELLM", True):
                patcher, fake_litellm = self._install_fake_litellm()
                with patcher:
                    config = AIConfig(model="deepseek/deepseek-chat")
                    mock_response = MagicMock()
                    mock_response.choices = [MagicMock()]
                    mock_response.choices[0].message.content = None
                    fake_litellm.completion.return_value = mock_response

                    client = AIClient(config)
                    result = client.generate_text("system prompt", "user prompt")

                    assert result is None

    def test_generate_text_with_extra_params(self) -> None:
        """Test generation with extra parameters."""
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            with patch("vibe3.clients.ai_client.HAS_LITELLM", True):
                patcher, fake_litellm = self._install_fake_litellm()
                with patcher:
                    config = AIConfig(model="deepseek/deepseek-chat")
                    mock_response = MagicMock()
                    mock_response.choices = [MagicMock()]
                    mock_response.choices[0].message.content = "result"
                    fake_litellm.completion.return_value = mock_response

                    client = AIClient(config)
                    result = client.generate_text(
                        "system prompt", "user prompt", temperature=0.7, max_tokens=100
                    )

                    assert result == "result"
                    call_kwargs = fake_litellm.completion.call_args[1]
                    assert "temperature" in call_kwargs
                    assert "max_tokens" in call_kwargs

    def test_uses_environment_key_name_from_config(self) -> None:
        """Test that client uses the environment variable name from config."""
        with patch.dict(os.environ, {"CUSTOM_API_KEY": "custom-key"}, clear=True):
            with patch("vibe3.clients.ai_client.HAS_LITELLM", True):
                config = AIConfig(
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
                config = AIConfig(model="deepseek/deepseek-chat")
                client = AIClient(config)
                assert client._api_key is None

    def test_generate_text_without_litellm_returns_none(self) -> None:
        """Test generation when litellm is not installed."""
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            with patch("vibe3.clients.ai_client.HAS_LITELLM", False):
                config = AIConfig(model="deepseek/deepseek-chat")
                client = AIClient(config)
                result = client.generate_text("system prompt", "user prompt")
                assert result is None
