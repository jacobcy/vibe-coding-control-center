"""AI service for text generation suggestions."""

from pathlib import Path

import yaml
from loguru import logger

from vibe3.clients.ai_client import AIClient
from vibe3.config.settings import AIConfig

DEFAULT_PROMPTS = {
    "flow": {
        "slug_suggestion": {
            "system": "You are an assistant that generates concise flow slugs.",
            "user": (
                "Issue: {issue_title}\n\n{issue_body}\n\n"
                "Generate 3 flow slug suggestions (kebab-case). "
                "Each suggestion should be on a separate line. "
                "Do not include numbers, bullets, or explanations."
            ),
        }
    },
    "pr": {
        "title_suggestion": {
            "system": "You are an assistant that generates PR titles.",
            "user": (
                "Commits:\n{commits}\n\n{changed_files}\n\n"
                "Generate a single PR title following conventional commit format. "
                "Do not include explanations."
            ),
        },
        "body_suggestion": {
            "system": "You are an assistant that generates PR descriptions.",
            "user": (
                "Commits:\n{commits}\n\n{changed_files}\n\n"
                "Generate a PR description with:\n"
                "1. Summary (1-2 sentences)\n"
                "2. Changes (bullet list)\n"
                "3. Testing (how to verify)\n\n"
                "Use markdown format."
            ),
        },
    },
}


class AIService:
    """Service for AI-assisted text generation.

    Provides business-level APIs for flow slug suggestions and PR content.
    """

    def __init__(
        self,
        config: AIConfig,
        prompts_path: Path | None = None,
    ) -> None:
        """Initialize AI service.

        Args:
            config: AI configuration
            prompts_path: Path to prompts.yaml file (optional)
        """
        self.config = config
        self.prompts = self._load_prompts(prompts_path)
        self.ai_client: AIClient | None = None

        self.ai_client = AIClient(config)
        if self.ai_client._api_key is None:
            self.ai_client = None
            logger.bind(module="ai_service").debug(
                "AI client not available, service will return None"
            )

    def _load_prompts(self, prompts_path: Path | None) -> dict:
        """Load prompts from YAML file or use defaults.

        Args:
            prompts_path: Path to prompts.yaml file

        Returns:
            Dict with prompts configuration
        """
        if prompts_path and prompts_path.exists():
            try:
                with open(prompts_path) as f:
                    loaded = yaml.safe_load(f)
                    if loaded:
                        return dict(loaded)
            except yaml.YAMLError:
                logger.bind(module="ai_service").warning(
                    f"Invalid YAML in {prompts_path}, using defaults"
                )
            except OSError as e:
                logger.bind(module="ai_service").warning(
                    f"Cannot read {prompts_path}: {e}, using defaults"
                )

        return DEFAULT_PROMPTS.copy()

    def suggest_flow_slug(
        self,
        issue_title: str,
        issue_body: str | None = None,
    ) -> list[str] | None:
        """Suggest flow slugs based on issue title and body.

        Args:
            issue_title: Issue title
            issue_body: Issue body (optional)

        Returns:
            List of suggested slugs or None if generation fails
        """
        if self.ai_client is None:
            return None

        prompt_config = self.prompts.get("flow", {}).get("slug_suggestion", {})
        system_prompt = prompt_config.get(
            "system", DEFAULT_PROMPTS["flow"]["slug_suggestion"]["system"]
        )
        user_template = prompt_config.get(
            "user", DEFAULT_PROMPTS["flow"]["slug_suggestion"]["user"]
        )

        body_text = issue_body if issue_body else ""
        user_prompt = user_template.format(
            issue_title=issue_title,
            issue_body=body_text,
        )

        result = self.ai_client.generate_text(system_prompt, user_prompt)
        if not result:
            return None

        slugs = [
            line.strip().lower() for line in result.strip().split("\n") if line.strip()
        ]

        if not slugs:
            return None

        logger.bind(module="ai_service").debug(
            f"Generated {len(slugs)} flow slug suggestions"
        )
        return slugs

    def suggest_pr_content(
        self,
        commits: list[str],
        changed_files: list[str] | None = None,
    ) -> tuple[str | None, str | None] | None:
        """Suggest PR title and body based on commits.

        Args:
            commits: List of commit messages
            changed_files: List of changed files (optional)

        Returns:
            Tuple of (title, body) or None if generation fails
        """
        if self.ai_client is None:
            return None

        commits_text = "\n".join(f"- {c}" for c in commits)
        files_text = "\n".join(f"- {f}" for f in changed_files) if changed_files else ""

        title_config = self.prompts.get("pr", {}).get("title_suggestion", {})
        title_system = title_config.get(
            "system", DEFAULT_PROMPTS["pr"]["title_suggestion"]["system"]
        )
        title_template = title_config.get(
            "user", DEFAULT_PROMPTS["pr"]["title_suggestion"]["user"]
        )

        title_result = self.ai_client.generate_text(
            title_system,
            title_template.format(commits=commits_text, changed_files=files_text),
        )
        if not title_result:
            return None

        body_config = self.prompts.get("pr", {}).get("body_suggestion", {})
        body_system = body_config.get(
            "system", DEFAULT_PROMPTS["pr"]["body_suggestion"]["system"]
        )
        body_template = body_config.get(
            "user", DEFAULT_PROMPTS["pr"]["body_suggestion"]["user"]
        )

        body_result = self.ai_client.generate_text(
            body_system,
            body_template.format(commits=commits_text, changed_files=files_text),
        )

        logger.bind(module="ai_service").debug("Generated PR content suggestions")
        return (title_result.strip(), body_result.strip() if body_result else None)
