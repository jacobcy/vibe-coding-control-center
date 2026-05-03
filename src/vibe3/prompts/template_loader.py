"""Helpers for loading configurable prompt templates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from loguru import logger

DEFAULT_PROMPTS_PATH = Path("config/prompts/prompts.yaml")


def _resolve_prompts_path() -> Path:
    """Resolve prompts.yaml path, preferring repo root over cwd."""
    # 1. Explicitly check if we are in a repo structure by traversing up from __file__
    # src/vibe3/prompts/template_loader.py -> parent x4 -> root
    try:
        repo_root = Path(__file__).resolve().parent.parent.parent.parent
        # Try new path first
        new_repo_path = repo_root / "config" / "prompts" / "prompts.yaml"
        if new_repo_path.exists():
            return new_repo_path
        # Fallback to old path with deprecation warning
        old_repo_path = repo_root / "config" / "prompts.yaml"
        if old_repo_path.exists():
            logger.bind(domain="prompt_templates", path=str(old_repo_path)).warning(
                "Using deprecated prompts path config/prompts.yaml. "
                "Please migrate to config/prompts/prompts.yaml"
            )
            return old_repo_path
    except Exception:  # pragma: no cover
        pass

    # 2. Fallback to CWD-relative path (already updated to new location)
    return DEFAULT_PROMPTS_PATH


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

- Supervisor: {supervisor_name}

{supervisor_content}

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
        "supervisor": {"apply": """# Supervisor Apply Scan

## Supervisor Material

- Supervisor: {supervisor_name}

{supervisor_content}

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

你当前处于 supervisor/apply 场景。只围绕 Supervisor 材料处理 handoff 或治理 issue。
不要进入 governance 巡检模式，也不要进入 run / plan / review 执行模式。
"""},
    },
}


def load_prompt_templates(prompts_path: Path | None = None) -> dict[str, Any]:
    """Load prompt templates from config/prompts.yaml with defaults."""
    path = prompts_path or _resolve_prompts_path()
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
