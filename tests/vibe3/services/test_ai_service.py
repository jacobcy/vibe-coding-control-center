"""Tests for AI service."""

from pathlib import Path
from unittest.mock import patch

from vibe3.clients.ai_client import AIClient
from vibe3.config.settings import AIConfig
from vibe3.services.ai_service import AIService


class TestAIService:
    """Tests for AIService class."""

    def test_init_with_api_key_creates_client(self, tmp_path: Path) -> None:
        """Test initialization when API key exists."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            config = AIConfig(api_key_env="OPENAI_API_KEY")
            service = AIService(config, prompts_path=tmp_path / "prompts.yaml")
            assert service.ai_client is not None

    def test_suggest_flow_slug_without_api_key_returns_none(
        self, tmp_path: Path
    ) -> None:
        """Test flow slug suggestion when AI client is unavailable."""
        config = AIConfig(api_key_env="OPENAI_API_KEY")
        service = AIService(config, prompts_path=tmp_path / "prompts.yaml")
        result = service.suggest_flow_slug("Add feature", "Description")
        assert result is None

    def test_suggest_flow_slug_success(self, tmp_path: Path) -> None:
        """Test successful flow slug suggestion."""
        prompts_file = tmp_path / "prompts.yaml"
        prompts_file.write_text("""
flow:
  slug_suggestion:
    system: "You are a helpful assistant."
    user: "Issue: {issue_title}"
""")

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            config = AIConfig(api_key_env="OPENAI_API_KEY")
            with patch.object(AIClient, "generate_text") as mock_generate:
                mock_generate.return_value = "feature-name\nanother-name\nthird-name"
                service = AIService(config, prompts_path=prompts_file)
                result = service.suggest_flow_slug("Add feature X")

                assert result == ["feature-name", "another-name", "third-name"]
                mock_generate.assert_called_once()

    def test_suggest_flow_slug_with_body(self, tmp_path: Path) -> None:
        """Test flow slug suggestion with issue body."""
        prompts_file = tmp_path / "prompts.yaml"
        prompts_file.write_text("""
flow:
  slug_suggestion:
    system: "You are a helpful assistant."
    user: "Issue: {issue_title}\n\n{issue_body}"
""")

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            config = AIConfig(api_key_env="OPENAI_API_KEY")
            with patch.object(AIClient, "generate_text") as mock_generate:
                mock_generate.return_value = "slug-name"
                service = AIService(config, prompts_path=prompts_file)
                result = service.suggest_flow_slug("Title", "Body content")

                assert result == ["slug-name"]
                call_args = mock_generate.call_args
                assert "Title" in call_args[0][1]
                assert "Body content" in call_args[0][1]

    def test_suggest_flow_slug_empty_result_returns_none(self, tmp_path: Path) -> None:
        """Test flow slug with empty result returns None."""
        prompts_file = tmp_path / "prompts.yaml"
        prompts_file.write_text("""
flow:
  slug_suggestion:
    system: "You are a helpful assistant."
    user: "Issue: {issue_title}"
""")

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            config = AIConfig(api_key_env="OPENAI_API_KEY")
            with patch.object(AIClient, "generate_text") as mock_generate:
                mock_generate.return_value = ""
                service = AIService(config, prompts_path=prompts_file)
                result = service.suggest_flow_slug("Title")

                assert result is None

    def test_suggest_flow_slug_api_fails_returns_none(self, tmp_path: Path) -> None:
        """Test flow slug when API fails returns None."""
        prompts_file = tmp_path / "prompts.yaml"
        prompts_file.write_text("""
flow:
  slug_suggestion:
    system: "You are a helpful assistant."
    user: "Issue: {issue_title}"
""")

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            config = AIConfig(api_key_env="OPENAI_API_KEY")
            with patch.object(AIClient, "generate_text") as mock_generate:
                mock_generate.return_value = None
                service = AIService(config, prompts_path=prompts_file)
                result = service.suggest_flow_slug("Title")

                assert result is None

    def test_suggest_pr_content_without_api_key_returns_none(
        self, tmp_path: Path
    ) -> None:
        """Test PR content suggestion when AI client is unavailable."""
        config = AIConfig(api_key_env="OPENAI_API_KEY")
        service = AIService(config, prompts_path=tmp_path / "prompts.yaml")
        result = service.suggest_pr_content(["commit 1", "commit 2"])
        assert result is None

    def test_suggest_pr_content_success(self, tmp_path: Path) -> None:
        """Test successful PR content suggestion."""
        prompts_file = tmp_path / "prompts.yaml"
        prompts_file.write_text("""
pr:
  title_suggestion:
    system: "You are a helpful assistant."
    user: "Commits: {commits}"
  body_suggestion:
    system: "You are a helpful assistant."
    user: "Commits: {commits}"
""")

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            config = AIConfig(api_key_env="OPENAI_API_KEY")
            with patch.object(AIClient, "generate_text") as mock_generate:
                mock_generate.side_effect = ["feat: add feature", "Summary\n\nChanges:"]
                service = AIService(config, prompts_path=prompts_file)
                result = service.suggest_pr_content(["commit 1", "commit 2"])

                assert result is not None
                title, body = result
                assert title == "feat: add feature"
                assert body == "Summary\n\nChanges:"

    def test_suggest_pr_content_with_changed_files(self, tmp_path: Path) -> None:
        """Test PR content suggestion with changed files."""
        prompts_file = tmp_path / "prompts.yaml"
        prompts_file.write_text("""
pr:
  title_suggestion:
    system: "You are a helpful assistant."
    user: "Commits: {commits}\n{changed_files}"
  body_suggestion:
    system: "You are a helpful assistant."
    user: "Commits: {commits}\n{changed_files}"
""")

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            config = AIConfig(api_key_env="OPENAI_API_KEY")
            with patch.object(AIClient, "generate_text") as mock_generate:
                mock_generate.side_effect = ["title", "body"]
                service = AIService(config, prompts_path=prompts_file)
                service.suggest_pr_content(
                    commits=["commit 1"],
                    changed_files=["src/file1.py", "src/file2.py"],
                )

                assert mock_generate.call_count == 2

    def test_suggest_pr_content_title_fails_returns_none(self, tmp_path: Path) -> None:
        """Test PR content when title generation fails."""
        prompts_file = tmp_path / "prompts.yaml"
        prompts_file.write_text("""
pr:
  title_suggestion:
    system: "You are a helpful assistant."
    user: "Commits: {commits}"
  body_suggestion:
    system: "You are a helpful assistant."
    user: "Commits: {commits}"
""")

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            config = AIConfig(api_key_env="OPENAI_API_KEY")
            with patch.object(AIClient, "generate_text") as mock_generate:
                mock_generate.return_value = None
                service = AIService(config, prompts_path=prompts_file)
                result = service.suggest_pr_content(["commit 1"])

                assert result is None

    def test_suggest_pr_content_body_fails_returns_title_only(
        self, tmp_path: Path
    ) -> None:
        """Test PR content when only title succeeds."""
        prompts_file = tmp_path / "prompts.yaml"
        prompts_file.write_text("""
pr:
  title_suggestion:
    system: "You are a helpful assistant."
    user: "Commits: {commits}"
  body_suggestion:
    system: "You are a helpful assistant."
    user: "Commits: {commits}"
""")

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            config = AIConfig(api_key_env="OPENAI_API_KEY")
            with patch.object(AIClient, "generate_text") as mock_generate:
                mock_generate.side_effect = ["title", None]
                service = AIService(config, prompts_path=prompts_file)
                result = service.suggest_pr_content(["commit 1"])

                assert result is not None
                title, body = result
                assert title == "title"
                assert body is None

    def test_missing_prompts_file_uses_defaults(self, tmp_path: Path) -> None:
        """Test that missing prompts file uses default prompts."""
        prompts_file = tmp_path / "nonexistent.yaml"
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            config = AIConfig(api_key_env="OPENAI_API_KEY")
            service = AIService(config, prompts_path=prompts_file)

            assert service.ai_client is not None
            assert "flow" in service.prompts
            assert "pr" in service.prompts

    def test_invalid_yaml_uses_defaults(self, tmp_path: Path) -> None:
        """Test that invalid YAML uses default prompts."""
        prompts_file = tmp_path / "invalid.yaml"
        prompts_file.write_text("invalid: yaml: content:")

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            config = AIConfig(api_key_env="OPENAI_API_KEY")
            service = AIService(config, prompts_path=prompts_file)

            assert "flow" in service.prompts
            assert "pr" in service.prompts
