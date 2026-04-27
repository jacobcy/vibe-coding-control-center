# Spec: Environment Variable Override for models.json

## Overview

允许通过环境变量覆盖 `config/models.json` 的 backend/model 配置，支持灵活部署。

## Priority Chain

```
env var > models.json > default fallback
```

## Environment Variables

### Global Defaults

| Env Var | Target | Example |
|---------|--------|---------|
| `VIBE_DEFAULT_BACKEND` | `default_backend` | `gemini` |
| `VIBE_DEFAULT_MODEL` | `default_model` | `gemini-3-flash-preview` |

### Agent-Specific Overrides

| Env Var Pattern | Target | Example |
|-----------------|--------|---------|
| `VIBE_BACKEND_<ROLE>` | Agent backend | `VIBE_BACKEND_MANAGER=claude` |
| `VIBE_MODEL_<ROLE>` | Agent model | `VIBE_MODEL_PLANNER=sonnet` |

Role name: `vibe-manager` → `MANAGER` (uppercase, strip prefix)

## keys.env Integration

```bash
# config/keys.env (loaded by direnv)
export VIBE_DEFAULT_BACKEND="gemini"
export VIBE_BACKEND_MANAGER="claude"
export VIBE_MODEL_MANAGER="sonnet"
```

## Implementation

### File: `src/vibe3/agents/backends/codeagent_config.py`

#### Function: `resolve_repo_agent_preset()`

```python
def resolve_repo_agent_preset(agent_name: str) -> tuple[str | None, str | None] | None:
    # 1. Check env var override
    role = agent_name.replace("vibe-", "").upper()
    env_backend = os.environ.get(f"VIBE_BACKEND_{role}")
    env_model = os.environ.get(f"VIBE_MODEL_{role}")
    if env_backend or env_model:
        return (env_backend or None, env_model or None)

    # 2. Fall back to models.json (existing logic)
    data = _read_models_json(repo_models_json_path())
    # ...
```

#### Function: `_read_models_json()` - Add global env defaults

```python
def _read_models_json(path: Path) -> dict[str, Any]:
    data = ...
    # Apply global env defaults
    if "VIBE_DEFAULT_BACKEND" in os.environ:
        data["default_backend"] = os.environ["VIBE_DEFAULT_BACKEND"]
    if "VIBE_DEFAULT_MODEL" in os.environ:
        data["default_model"] = os.environ["VIBE_DEFAULT_MODEL"]
    return data
```

## Test Cases

1. No env vars → use models.json
2. `VIBE_BACKEND_MANAGER=claude` → manager uses claude
3. `VIBE_DEFAULT_BACKEND=gemini` → all agents fallback to gemini
4. Both set → agent-specific wins over default

## Effort

- 代码修改：`codeagent_config.py` (~20 lines)
- 测试：`test_codeagent_config.py` (~30 lines)
- 预计时间：30 分钟
