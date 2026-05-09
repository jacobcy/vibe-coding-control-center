"""Tests for vibe3.utils.codeagent_helpers."""

from vibe3.utils.codeagent_helpers import sanitize_prompt_for_display


class TestSanitizePromptForDisplay:
    """Test suite for sanitize_prompt_for_display function."""

    def test_sanitizes_openai_api_key(self) -> None:
        """OpenAI API keys should be sanitized with prefix preserved."""
        text = "API key: sk-proj-abc123def456ghi789jkl012mno345pqr678"
        result = sanitize_prompt_for_display(text)
        assert "sk-proj-***REDACTED***" in result
        assert "sk-proj-abc123def456ghi789jkl012mno345pqr678" not in result

    def test_sanitizes_openai_api_key_short_prefix(self) -> None:
        """OpenAI API keys with short prefix should be sanitized."""
        text = "Key: sk-abc123def456ghi789jkl012mno345pqr678"
        result = sanitize_prompt_for_display(text)
        assert "sk-***REDACTED***" in result
        assert "sk-abc123def456ghi789jkl012mno345pqr678" not in result

    def test_sanitizes_aws_access_key(self) -> None:
        """AWS access keys should be sanitized with prefix preserved."""
        text = "AWS key: AKIAIOSFODNN7EXAMPLE"
        result = sanitize_prompt_for_display(text)
        assert "AKIA***REDACTED***" in result
        assert "AKIAIOSFODNN7EXAMPLE" not in result

    def test_sanitizes_github_token(self) -> None:
        """GitHub tokens should be sanitized with prefix preserved."""
        text = "Token: ghp_1234567890abcdefghijklmnopqrstuvwxyz123456"
        result = sanitize_prompt_for_display(text)
        assert "ghp_***REDACTED***" in result
        assert "ghp_1234567890abcdefghijklmnopqrstuvwxyz123456" not in result

    def test_sanitizes_github_token_other_prefixes(self) -> None:
        """GitHub tokens with other prefixes (gho_, ghu_, etc.) should be sanitized."""
        prefixes = ["gho_", "ghu_", "ghs_", "ghr_"]
        for prefix in prefixes:
            text = f"Token: {prefix}{'a' * 36}"
            result = sanitize_prompt_for_display(text)
            assert f"{prefix}***REDACTED***" in result
            assert f"{prefix}{'a' * 36}" not in result

    def test_sanitizes_generic_key_value_pairs(self) -> None:
        """Generic key/value pairs should be sanitized."""
        # api_key with colon
        text = "Configuration:\napi_key: my_secret_key_12345"
        result = sanitize_prompt_for_display(text)
        assert "api_key***REDACTED***" in result
        assert "my_secret_key_12345" not in result

        # secret_key with equals
        text2 = "secret_key=another_secret_value"
        result2 = sanitize_prompt_for_display(text2)
        assert "secret_key***REDACTED***" in result2
        assert "another_secret_value" not in result2

        # access_token with colon
        text3 = "access_token: bearer_token_xyz"
        result3 = sanitize_prompt_for_display(text3)
        assert "access_token***REDACTED***" in result3
        assert "bearer_token_xyz" not in result3

        # auth_token with equals
        text4 = "auth_token=auth_value_789"
        result4 = sanitize_prompt_for_display(text4)
        assert "auth_token***REDACTED***" in result4
        assert "auth_value_789" not in result4

        # private_key with colon
        text5 = "private_key: private_key_data"
        result5 = sanitize_prompt_for_display(text5)
        assert "private_key***REDACTED***" in result5
        assert "private_key_data" not in result5

    def test_sanitizes_generic_key_case_insensitive(self) -> None:
        """Generic key patterns should be case-insensitive."""
        text = "API_KEY: secret123\nApiKey: secret456\nSECRET_KEY: secret789"
        result = sanitize_prompt_for_display(text)
        assert "API_KEY***REDACTED***" in result
        assert "ApiKey***REDACTED***" in result
        assert "SECRET_KEY***REDACTED***" in result
        assert "secret123" not in result
        assert "secret456" not in result
        assert "secret789" not in result

    def test_sanitizes_bearer_token(self) -> None:
        """Bearer tokens should be sanitized with prefix preserved."""
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload"
        result = sanitize_prompt_for_display(text)
        assert "Bearer ***REDACTED***" in result
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result

    def test_preserves_non_sensitive_content(self) -> None:
        """Text without secrets should pass through unchanged."""
        text = "This is a normal prompt with no secrets.\nLine 2: some random text."
        result = sanitize_prompt_for_display(text)
        assert result == text

    def test_handles_multiple_secrets(self) -> None:
        """Multiple secrets in one text should all be sanitized."""
        text = """
        API key: sk-proj-abc123def456ghi789jkl012mno345pqr678
        AWS key: AKIAIOSFODNN7EXAMPLE
        GitHub token: ghp_1234567890abcdefghijklmnopqrstuvwxyz123456
        Regular text here.
        Bearer: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload
        api_key: my_secret_key
        """
        result = sanitize_prompt_for_display(text)

        assert "sk-proj-***REDACTED***" in result
        assert "AKIA***REDACTED***" in result
        assert "ghp_***REDACTED***" in result
        assert "Bearer ***REDACTED***" in result
        assert "api_key***REDACTED***" in result
        assert "Regular text here." in result

        assert "sk-proj-abc123def456ghi789jkl012mno345pqr678" not in result
        assert "AKIAIOSFODNN7EXAMPLE" not in result
        assert "ghp_1234567890abcdefghijklmnopqrstuvwxyz123456" not in result
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result
        assert "my_secret_key" not in result

    def test_preserves_prompt_structure(self) -> None:
        """Redaction should not break markdown formatting."""
        text = """# Task Instructions

Use the API key: sk-proj-abc123def456ghi789jkl012mno345pqr678

## Section
- Item 1
- Item 2

```python
api_key = "sk-proj-xyz789abc456def012ghi345jkl678mno901"
```
"""
        result = sanitize_prompt_for_display(text)

        # Structure preserved
        assert "# Task Instructions" in result
        assert "## Section" in result
        assert "- Item 1" in result
        assert "```python" in result

        # Secrets sanitized
        assert "sk-proj-***REDACTED***" in result
        assert "sk-proj-abc123def456ghi789jkl012mno345pqr678" not in result
        assert "sk-proj-xyz789abc456def012ghi345jkl678mno901" not in result

    def test_short_secrets_not_redacted(self) -> None:
        """Secrets below minimum length should not be redacted.

        This avoids false positives.
        """
        # OpenAI key too short (< 20 chars after sk-)
        text = "Key: sk-short"
        result = sanitize_prompt_for_display(text)
        assert result == text  # Should pass through unchanged

        # AWS key too short (< 16 chars after AKIA)
        text2 = "Key: AKIAIOSFODNN"
        result2 = sanitize_prompt_for_display(text2)
        assert "AKIAIOSFODNN" in result2  # Should pass through unchanged

        # GitHub token too short (< 36 chars after prefix)
        text3 = "Token: ghp_tooshort"
        result3 = sanitize_prompt_for_display(text3)
        assert result3 == text3  # Should pass through unchanged

        # Bearer token too short (< 20 chars)
        text4 = "Auth: Bearer short"
        result4 = sanitize_prompt_for_display(text4)
        assert result4 == text4  # Should pass through unchanged
