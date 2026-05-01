"""Tests for error classification functions."""

import asyncio

from vibe3.exceptions import AgentExecutionError, AgentPresetNotFoundError
from vibe3.exceptions.error_classification import (
    E_API_NETWORK,
    E_API_RATE_LIMIT,
    E_API_TIMEOUT,
    E_EXEC_UNKNOWN,
    E_MODEL_CONFIG,
    E_MODEL_NOT_FOUND,
    classify_error,
    classify_error_from_exception,
    classify_error_hybrid,
)


class TestClassifyErrorFromException:
    """Test classify_error_from_exception function."""

    def test_timeout_error(self) -> None:
        """Test TimeoutError classification."""
        exc = TimeoutError("timed out")
        assert classify_error_from_exception(exc) == E_API_TIMEOUT

    def test_asyncio_timeout_error(self) -> None:
        """Test asyncio.TimeoutError classification."""
        exc = asyncio.TimeoutError("async timed out")
        assert classify_error_from_exception(exc) == E_API_TIMEOUT

    def test_connection_error(self) -> None:
        """Test ConnectionError classification."""
        exc = ConnectionError("connection refused")
        assert classify_error_from_exception(exc) == E_API_NETWORK

    def test_connection_refused_error(self) -> None:
        """Test ConnectionRefusedError classification (subclass of ConnectionError)."""
        exc = ConnectionRefusedError("connection refused")
        assert classify_error_from_exception(exc) == E_API_NETWORK

    def test_unknown_exception(self) -> None:
        """Test unknown exception returns E_EXEC_UNKNOWN."""
        exc = ValueError("some error")
        assert classify_error_from_exception(exc) == E_EXEC_UNKNOWN

    def test_vibe3_exception_agent_preset_not_found(self) -> None:
        """Test AgentPresetNotFoundError classification."""
        exc = AgentPresetNotFoundError("missing-preset")
        assert classify_error_from_exception(exc) == E_MODEL_CONFIG

    def test_vibe3_exception_agent_execution_error(self) -> None:
        """Test AgentExecutionError classification."""
        exc = AgentExecutionError("execution failed")
        assert classify_error_from_exception(exc) == E_EXEC_UNKNOWN


class TestClassifyErrorHybrid:
    """Test classify_error_hybrid function."""

    def test_structured_first_timeout(self) -> None:
        """Test that structured classification is tried first."""
        # Known exception type - uses structured mapping
        exc = TimeoutError("timed out")
        assert classify_error_hybrid(exc) == E_API_TIMEOUT

    def test_fallback_to_string_matching(self) -> None:
        """Test fallback to string matching for unknown exceptions."""
        # Exception with name in string that classify_error recognizes
        exc = Exception("ProviderModelNotFoundError: model xyz not found")
        # Fallback string matching should find the pattern
        assert classify_error_hybrid(exc) == E_MODEL_NOT_FOUND

    def test_hybrid_unknown_error(self) -> None:
        """Test hybrid classification with unknown error."""
        exc = ValueError("random error")
        # Should fallback to string matching and return E_EXEC_UNKNOWN
        assert classify_error_hybrid(exc) == E_EXEC_UNKNOWN


class TestClassifyErrorUnchanged:
    """Test that existing classify_error behavior is unchanged."""

    def test_rate_limit_variations(self) -> None:
        """Test rate limit error classification."""
        assert classify_error("rate limit exceeded") == E_API_RATE_LIMIT
        assert classify_error("429 too many requests") == E_API_RATE_LIMIT

    def test_model_not_found(self) -> None:
        """Test model not found error classification."""
        assert classify_error("ProviderModelNotFoundError: xyz") == E_MODEL_NOT_FOUND

    def test_timeout(self) -> None:
        """Test timeout error classification."""
        assert classify_error("timeout exceeded") == E_API_TIMEOUT

    def test_network_error(self) -> None:
        """Test network error classification."""
        assert classify_error("network error occurred") == E_API_NETWORK

    def test_unknown(self) -> None:
        """Test unknown error classification."""
        assert classify_error("something random") == E_EXEC_UNKNOWN
