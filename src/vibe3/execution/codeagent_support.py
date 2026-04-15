"""Foundational helpers for command-level codeagent execution."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Sequence

from vibe3.config.settings import VibeConfig
from vibe3.models.review_runner import AgentOptions


def resolve_command_agent_options(
    *,
    config: VibeConfig,
    section: Literal["plan", "run", "review"],
    agent: str | None = None,
    backend: str | None = None,
    model: str | None = None,
) -> AgentOptions:
    """Resolve command agent options with CLI override support."""
    target_config = getattr(config, section, None)
    config_agent = None
    config_backend = None
    config_model = None
    config_timeout = 3600

    if target_config and hasattr(target_config, "agent_config"):
        agent_config = target_config.agent_config
        config_agent = getattr(agent_config, "agent", None)
        config_backend = getattr(agent_config, "backend", None)
        config_model = getattr(agent_config, "model", None)
        config_timeout = getattr(agent_config, "timeout_seconds", 3600)

    if agent:
        return AgentOptions(agent=agent, timeout_seconds=config_timeout)

    if backend:
        return AgentOptions(
            backend=backend,
            model=model,
            timeout_seconds=config_timeout,
        )

    if config_agent:
        return AgentOptions(
            agent=config_agent,
            timeout_seconds=config_timeout,
        )

    if config_backend:
        return AgentOptions(
            backend=config_backend,
            model=config_model,
            timeout_seconds=config_timeout,
        )

    raise ValueError(
        f"No agent configuration found for '{section}' command. "
        f"Configure agent_config in settings.yaml or use CLI options."
    )


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def build_self_invocation(args: Sequence[str]) -> list[str]:
    """Build baseline-project self-invocation for tmux child."""
    cmd = [
        "uv",
        "run",
        "--project",
        str(_repo_root()),
        "python",
        str(_repo_root() / "src" / "vibe3" / "cli.py"),
    ]
    saw_no_async_flag = False
    for arg in args:
        if arg == "--async":
            continue
        if arg == "--no-async":
            saw_no_async_flag = True
        cmd.append(arg)
    if not saw_no_async_flag:
        cmd.append("--no-async")
    return cmd
