"""Config resolution for codeagent backend.

Handles reading repo-local agent presets and syncing effective
backend/model settings to ``~/.codeagent/models.json``.
"""

import json
import os
import shutil
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
BACKEND_COMMANDS: Final[dict[str, str]] = {
    "claude": "claude",
    "codex": "codex",
    "gemini": "gemini",
    "opencode": "opencode",
}


def repo_models_json_path() -> Path:
    """Resolve repo-local models.json with optional orchestra root override."""
    override_root = os.environ.get("VIBE3_REPO_MODELS_ROOT", "").strip()
    if override_root:
        return Path(override_root).expanduser().resolve() / "config" / "models.json"
    return REPO_MODELS_JSON_PATH


def _read_models_json(path: Path) -> dict[str, Any]:
    """Read a models.json file and return a dict, or empty dict on failure.

    Applies global env var overrides for default_backend/default_model.
    """
    try:
        if path.exists():
            data = json.loads(path.read_text())
            if not isinstance(data, dict):
                return {}
        else:
            data = {}
    except Exception as exc:
        logger.bind(domain="review_runner", path=str(path)).warning(
            f"Failed to read models config: {exc}"
        )
        data = {}

    # Apply global env defaults
    if "VIBE_DEFAULT_BACKEND" in os.environ:
        data["default_backend"] = os.environ["VIBE_DEFAULT_BACKEND"]
    if "VIBE_DEFAULT_MODEL" in os.environ:
        data["default_model"] = os.environ["VIBE_DEFAULT_MODEL"]

    return data


def configured_backends(path: Path | None = None) -> set[str]:
    """Return all backend names actively referenced by repo models config."""
    data = _read_models_json(path or repo_models_json_path())
    backends: set[str] = set()

    default_backend = data.get("default_backend")
    if isinstance(default_backend, str) and default_backend.strip():
        backends.add(default_backend.strip())

    agents = data.get("agents")
    if isinstance(agents, dict):
        for raw in agents.values():
            if not isinstance(raw, dict):
                continue
            backend = raw.get("backend")
            if isinstance(backend, str) and backend.strip():
                backends.add(backend.strip())

    return backends


def find_missing_backend_commands(
    path: Path | None = None,
    *,
    env_path: str | None = None,
) -> dict[str, str]:
    """Return configured backends whose CLI command is missing from PATH."""
    missing: dict[str, str] = {}
    for backend in sorted(configured_backends(path)):
        command = BACKEND_COMMANDS.get(backend)
        if not command:
            continue
        if shutil.which(command, path=env_path) is None:
            missing[backend] = command
    return missing


def resolve_repo_agent_preset(
    agent_name: str,
) -> tuple[str | None, str | None] | None:
    """Resolve agent preset from repo-local config/models.json with env override.

    Priority:
    1. Environment variable override (VIBE_BACKEND_<ROLE>, VIBE_MODEL_<ROLE>)
    2. Repo-local config/models.json mapping

    Automatically tries with 'vibe-' prefix if direct lookup fails.

    Returns:
        (backend, model) when repo-local mapping exists, otherwise None.
    """
    # 1. Check env var override first
    role = agent_name.replace("vibe-", "").upper()
    env_backend = os.environ.get(f"VIBE_BACKEND_{role}")
    env_model = os.environ.get(f"VIBE_MODEL_{role}")
    if env_backend or env_model:
        logger.bind(
            domain="codeagent_config",
            agent=agent_name,
            backend=env_backend,
            model=env_model,
        ).debug("Using env var override for agent preset")
        return (env_backend or None, env_model or None)

    # 2. Fall back to models.json
    data = _read_models_json(repo_models_json_path())
    agents = data.get("agents")
    if not isinstance(agents, dict):
        return None

    # Try direct lookup first
    raw = agents.get(agent_name)
    if not isinstance(raw, dict):
        # Try with 'vibe-' prefix if direct lookup fails
        prefixed_name = f"vibe-{agent_name}"
        raw = agents.get(prefixed_name)
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
    3. Fallback to default_backend/default_model from models.json
    4. Raise error if no fallback available

    Returns backend/model for database recording and sync operations.
    """
    if options.backend:
        return options
    if not options.agent:
        return options
    resolved = resolve_repo_agent_preset(options.agent)
    if not resolved:
        data = _read_models_json(repo_models_json_path())
        default_backend = data.get("default_backend")
        default_model = data.get("default_model")
        if default_backend and isinstance(default_backend, str):
            logger.bind(domain="codeagent_config").warning(
                f"Agent preset '{options.agent}' not found in config/models.json, "
                f"falling back to default: {default_backend}/{default_model}"
            )
            return AgentOptions(
                agent=None,
                backend=default_backend,
                model=str(default_model) if isinstance(default_model, str) else None,
                timeout_seconds=options.timeout_seconds,
            )
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
