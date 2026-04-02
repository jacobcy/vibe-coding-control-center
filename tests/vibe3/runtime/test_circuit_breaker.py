"""Tests for CircuitBreaker and error classification."""

from vibe3.runtime.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    classify_failure,
)


class TestClassifyFailure:
    """Tests for error classification."""

    def test_api_error_rate_limit(self):
        """Rate limit errors should be classified as api_error."""
        category = classify_failure(1, "Error: rate limit exceeded")
        assert category == "api_error"

    def test_api_error_token(self):
        """Token errors should be classified as api_error."""
        category = classify_failure(1, "Error: insufficient token quota")
        assert category == "api_error"

    def test_api_error_429(self):
        """HTTP 429 should be classified as api_error."""
        category = classify_failure(1, "HTTP 429 Too Many Requests")
        assert category == "api_error"

    def test_api_error_context_length(self):
        """Context length errors should be classified as api_error."""
        category = classify_failure(1, "Error: context length exceeded")
        assert category == "api_error"

    def test_api_error_timeout(self):
        """Timeout errors should be classified as api_error."""
        category = classify_failure(1, "Error: timeout waiting for response")
        assert category == "api_error"

    def test_business_error_merge_conflict(self):
        """Merge conflicts should NOT trigger circuit breaker."""
        category = classify_failure(1, "Error: merge conflict in file.py")
        assert category == "business_error"

    def test_business_error_test_failed(self):
        """Test failures should NOT trigger circuit breaker."""
        category = classify_failure(1, "Error: test failed after 3 retries")
        assert category == "business_error"

    def test_business_error_review_rejected(self):
        """Review rejections should NOT trigger circuit breaker."""
        category = classify_failure(1, "PR review rejected")
        assert category == "business_error"

    def test_timeout_error(self):
        """Timeouts should be classified distinctly and count toward breaker."""
        category = classify_failure(1, "command timed out", timed_out=True)
        assert category == "timeout"

    def test_unknown_error(self):
        """Unknown errors should count toward breaker (conservative)."""
        category = classify_failure(1, "Something went wrong")
        assert category == "unknown"


class TestCircuitBreaker:
    """Tests for CircuitBreaker state machine."""

    def test_initial_state_closed(self):
        """Circuit breaker starts in CLOSED state."""
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.state_value == "closed"
        assert cb.allow_request() is True

    def test_closed_allows_requests(self):
        """CLOSED state should allow all requests."""
        cb = CircuitBreaker()
        assert cb.allow_request() is True
        assert cb.allow_request() is True
        assert cb.allow_request() is True

    def test_record_success_resets_to_closed(self):
        """Success should reset breaker to CLOSED."""
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_failure("api_error")
        cb.record_failure("api_error")
        assert cb.state == CircuitState.OPEN

        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_threshold_triggers_open(self):
        """N failures should transition to OPEN."""
        cb = CircuitBreaker(failure_threshold=3)
        assert cb.state == CircuitState.CLOSED

        cb.record_failure("api_error")
        assert cb.state == CircuitState.CLOSED

        cb.record_failure("api_error")
        assert cb.state == CircuitState.CLOSED

        cb.record_failure("api_error")
        assert cb.state == CircuitState.OPEN

    def test_open_blocks_requests(self):
        """OPEN state should block requests."""
        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=300)
        cb.record_failure("api_error")
        assert cb.state == CircuitState.OPEN
        assert cb.allow_request() is False

    def test_business_errors_dont_count(self):
        """Business errors should not increment failure count."""
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_failure("business_error")
        cb.record_failure("business_error")
        cb.record_failure("business_error")
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_half_open_after_cooldown(self, monkeypatch):
        """After cooldown, should transition to HALF_OPEN."""
        import time

        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=10)
        cb.record_failure("api_error")
        assert cb.state == CircuitState.OPEN

        # Simulate time passing
        monkeypatch.setattr(time, "time", lambda: cb.last_failure_time + 11)
        assert cb.allow_request() is True
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_success_closes(self, monkeypatch):
        """Success in HALF_OPEN should transition to CLOSED."""
        import time

        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=10)
        cb.record_failure("api_error")
        monkeypatch.setattr(time, "time", lambda: cb.last_failure_time + 11)
        cb.allow_request()  # Transition to HALF_OPEN

        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_reopens(self, monkeypatch):
        """Failure in HALF_OPEN should go back to OPEN."""
        import time

        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=10)
        cb.record_failure("api_error")
        monkeypatch.setattr(time, "time", lambda: cb.last_failure_time + 11)
        cb.allow_request()  # Transition to HALF_OPEN

        cb.record_failure("api_error")
        assert cb.state == CircuitState.OPEN

    def test_half_open_max_tests(self):
        """HALF_OPEN should limit test requests."""
        cb = CircuitBreaker(
            failure_threshold=1,
            cooldown_seconds=0,  # Immediately allow HALF_OPEN
            half_open_max_tests=1,
        )
        cb.record_failure("api_error")
        # Force to HALF_OPEN
        cb.state = CircuitState.HALF_OPEN
        cb._half_open_tests = 0

        # First request allowed
        assert cb.allow_request() is True
        # Second request blocked
        assert cb.allow_request() is False

    def test_manual_reset(self):
        """Manual reset should return to CLOSED state."""
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure("api_error")
        cb.record_failure("api_error")
        assert cb.state == CircuitState.OPEN

        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert cb.last_failure_timestamp is None
