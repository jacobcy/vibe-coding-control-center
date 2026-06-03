"""Config resolution for codeagent backend.

Handles syncing effective backend/model settings to ``~/.codeagent/models.json``.
"""

import json
from pathlib import Path
from typing import Any, Final

from loguru import logger

from vibe3.config.agent_preset import (
    _read_models_json,
    repo_models_json_path,
    resolve_effective_agent_options,
)
from vibe3.models.review_runner import AgentOptions

# Path to codeagent models config
MODELS_JSON_PATH: Final[Path] = Path.home() / ".codeagent" / "models.json"


def sync_models_json(options: AgentOptions) -> None:
    """Sync effective backend/model and agents presets to ~/.codeagent/models.json.

    In backend mode: updates default_backend (and default_model if specified),
    so codeagent-wrapper uses vibe3's config instead of whatever is in the file.

    Also syncs the complete agents dictionary from repo config to ensure
    codeagent-wrapper can resolve agent presets with their yolo settings.
    """
    effective = resolve_effective_agent_options(options)
    if not effective.backend:
        return  # no repo-local backend mapping available

    try:
        existing: dict[str, Any] = {}
        if MODELS_JSON_PATH.exists():
            existing = json.loads(MODELS_JSON_PATH.read_text())
    except Exception as exc:
        logger.bind(domain="review_runner").warning(
            f"Failed to read models.json, will overwrite: {exc}"
        )
        existing = {}

    # Sync complete agents presets from repo config
    repo_data = _read_models_json(repo_models_json_path())
    repo_agents = repo_data.get("agents")
    if isinstance(repo_agents, dict) and repo_agents:
        # Merge repo agents into existing agents (repo takes precedence)
        existing_agents = existing.get("agents", {})
        if not isinstance(existing_agents, dict):
            existing_agents = {}
        existing_agents.update(repo_agents)
        existing["agents"] = existing_agents
        logger.bind(domain="review_runner").debug(
            f"Synced {len(repo_agents)} agent presets"
        )

    existing["default_backend"] = effective.backend
    if effective.model:
        existing["default_model"] = effective.model

    try:
        MODELS_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
        MODELS_JSON_PATH.write_text(json.dumps(existing, indent=2))
        logger.bind(
            domain="review_runner",
            backend=effective.backend,
            model=effective.model,
        ).debug("Synced models.json")
    except Exception as exc:
        logger.bind(domain="review_runner").warning(
            f"Failed to write models.json: {exc}"
        )
