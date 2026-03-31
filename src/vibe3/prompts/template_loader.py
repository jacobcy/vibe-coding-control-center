"""Helpers for loading configurable prompt templates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from loguru import logger

DEFAULT_PROMPTS_PATH = Path("config/prompts.yaml")
DEFAULT_PROMPT_TEMPLATES: dict[str, Any] = {
    "run": {
        "plan": "{run_prompt_body}",
        "skill": "{skill_content}",
    },
    "plan": {
        "default": "{plan_prompt_body}",
    },
    "review": {
        "default": "{review_prompt_body}",
    },
    "orchestra": {
        "assignee_dispatch": {
            "manager": "Implement issue #{issue_number}: {issue_title}",
        },
        "governance": {"plan": """# Orchestra Governance Scan

## Governance Material

- Skill: {skill_name}

{skill_content}

## Runtime Summary

- Server: {server_status}
- Running issues: {running_issue_count}
- Suggested issues: {suggested_issue_count}
- Active flows: {active_flows}
- Circuit breaker: {circuit_breaker_state} (failures={circuit_breaker_failures})

## Running Issues

{running_issue_details}

## Suggested Issues

仅供参考；最终仍需结合 flow / worktree / PR 现场判断。
{suggested_issue_details}

## 指令

请只围绕以下治理问题做判断：
1. 当前哪些 issue 已经在运行
2. 当前哪些 issue 值得建议启动
3. 是否需要最小 label 调整来表达上述判断
4. 如果暂不建议启动，说明原因
"""},
    },
}


def load_prompt_templates(prompts_path: Path | None = None) -> dict[str, Any]:
    """Load prompt templates from config/prompts.yaml with defaults."""
    path = prompts_path or DEFAULT_PROMPTS_PATH
    loaded: dict[str, Any] = {}
    if path.exists():
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                loaded = raw
        except yaml.YAMLError as exc:
            logger.bind(domain="prompt_templates", path=str(path)).warning(
                f"Invalid YAML in prompts file: {exc}"
            )
        except OSError as exc:
            logger.bind(domain="prompt_templates", path=str(path)).warning(
                f"Cannot read prompts file: {exc}"
            )
    return _deep_merge(DEFAULT_PROMPT_TEMPLATES, loaded)


def resolve_prompt_template(
    template_key: str,
    prompts_path: Path | None = None,
) -> str | None:
    """Resolve a dotted prompt template path from prompts.yaml."""
    current: Any = load_prompt_templates(prompts_path)
    for part in template_key.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
        if current is None:
            return None
    return current if isinstance(current, str) else None


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged
