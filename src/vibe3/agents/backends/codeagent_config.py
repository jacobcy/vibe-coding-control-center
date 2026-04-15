"""Config resolution for codeagent backend.

Handles reading repo-local agent presets and syncing effective
backend/model settings to ``~/.codeagent/models.json``.
"""

import json
import os
from pathlib import Path
from typing import Any, Final

from loguru import logger

from vibe3.exceptions import AgentPresetNotFoundError
from vibe3.models.review_runner import AgentOptions

# Path to codeagent models config
MODELS_JSON_PATH: Final[Path] = Path.home() / ".codeagent" / "models.json"
REPO_MODELS_JSON_PATH: Final[Path] = (
    Path(__file__).resolve().parents[4] / "config" / "models.json"
)


def repo_models_json_path() -> Path:
    """Resolve repo-local models.json with optional orchestra root override."""
    override_root = os.environ.get("VIBE3_REPO_MODELS_ROOT", "").strip()
    if override_root:
        return Path(override_root).expanduser().resolve() / "config" / "models.json"
    return REPO_MODELS_JSON_PATH


def _read_models_json(path: Path) -> dict[str, Any]:
    """Read a models.json file and return a dict, or empty dict on failure."""
    try:
        if path.exists():
            data = json.loads(path.read_text())
            if isinstance(data, dict):
                return data
    except Exception as exc:
        logger.bind(domain="review_runner", path=str(path)).warning(
            f"Failed to read models config: {exc}"
        )
    return {}


def resolve_repo_agent_preset(
    agent_name: str,
) -> tuple[str | None, str | None] | None:
    """Resolve agent preset from repo-local config/models.json.

    Returns:
        (backend, model) when repo-local mapping exists, otherwise None.
    """
    data = _read_models_json(repo_models_json_path())
    agents = data.get("agents")
    if not isinstance(agents, dict):
        return None
    raw = agents.get(agent_name)
    if not isinstance(raw, dict):
        return None
    backend = raw.get("backend")
    model = raw.get("model")
    if backend is not None and not isinstance(backend, str):
        backend = None
    if model is not None and not isinstance(model, str):
        model = None
    if backend is None and model is None:
        return None
    return backend, model


def resolve_effective_agent_options(options: AgentOptions) -> AgentOptions:
    """Resolve repo-local agent preset mapping into explicit backend/model.

    Priority:
    1. Explicit backend/model override in options
    2. Repo-local config/models.json mapping for agent preset
    3. Raise error if agent preset cannot be resolved

    Raises:
        AgentPresetNotFoundError: If agent preset not found in config/models.json
    """
    if options.backend:
        return options
    if not options.agent:
        return options
    resolved = resolve_repo_agent_preset(options.agent)
    if not resolved:
        raise AgentPresetNotFoundError(options.agent)
    backend, mapped_model = resolved
    return AgentOptions(
        agent=None,
        backend=backend,
        model=options.model or mapped_model,
        timeout_seconds=options.timeout_seconds,
    )


def sync_models_json(options: AgentOptions) -> None:
    """Sync effective backend/model to ~/.codeagent/models.json.

    In backend mode: updates default_backend (and default_model if specified),
    so codeagent-wrapper uses vibe3's config instead of whatever is in the file.

    In unmapped agent preset mode: no-op — codeagent manages the preset's
    backend/model from its own config. If a repo-local preset resolves to an
    explicit backend/model, this function syncs the resolved values.
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
