---
document_type: implementation-guide
title: Vibe 3.0 - Logging System
status: active
author: Claude Sonnet 4.6
created: 2026-03-15
last_updated: 2026-03-16
related_docs:
  - docs/standards/v3/handoff-store-standard.md
  - docs/standards/v3/github-remote-call-standard.md
  - docs/v3/infrastructure/02-architecture.md
  - docs/v3/infrastructure/03-coding-standards.md
---

# Vibe 3.0 - 日志系统 (Agent-Centric)

> **模块位置**: `observability/` - 日志、追踪、审计统一管理
> **追踪标准**: 见 [docs/v3/infrastructure/observability-standard.md](observability-standard.md)（待补充）

## 设计原则

**Agent 友好优先**：
- ✅ **结构化语义**：通过 `logger.bind()` 赋予日志明确的操作上下文
- ✅ **可追踪性**：强制使用 `logger.exception()` 记录完整错误堆栈
- ✅ **精准定位**：DEBUG 日志必须包含 `文件:行号:函数` 信息
- ✅ **控制台美化**：Rich 集成，提供直观的进度视觉反馈

---

## Observability 模块结构

```
src/vibe3/observability/
├── __init__.py
├── logger.py          # 日志配置（本文件档）
├── trace.py           # 追踪系统（--trace 支持）
└── audit.py           # 审计日志（预留）
```

**职责划分**:
- `logger.py`: 日志配置和格式化
- `trace.py`: 运行时调用链路追踪
- `audit.py`: 审计日志（面向未来）

---

## Agent 适配规范 (强制)

### 1. `logger.bind()` 标准字段绑定
每次逻辑操作或命令执行时，必须绑定标准字段以辅助 agent 识别操作链：

```python
# 每个命令入口或 Service 核心方法起始处
logger.bind(
    command="pr draft",      # 用户输入的原始命令
    domain="pr",             # 业务域 (pr/flow/task/handoff)
    action="create_draft",   # 当前执行的具体原子操作
).info("Initiating draft PR creation")
```

### 2. 结构化错误日志
禁止捕获异常后只记录文本。必须使用 `logger.exception()`，以便 agent 在读取日志时能直接拿到 Traceback 定位原因。

```python
# ✅ 推荐
try:
    client.call_api()
except GitHubError as e:
    logger.exception(f"GitHub API call failed: {e}")
    raise

# ❌ 禁止 (丢失 Traceback)
logger.error(f"Failed to call API: {e}")
```

---

## 完整实现

### 1. 初始化 (config/logging.py)

```python
import sys
from loguru import logger
from typing import Literal

def setup_logging(verbose: int = 0) -> None:
    """
    配置日志系统
    verbose=0: ERROR 级别 (简洁)
    verbose=1: INFO 级别 (带成功/信息提示)
    verbose=2: DEBUG 级别 (显示文件/行号, 详细输出)
    """
    logger.remove()
    
    level = "ERROR"
    if verbose == 1:
        level = "INFO"
    elif verbose >= 2:
        level = "DEBUG"

    # 控制台输出
    logger.add(
        sys.stderr,
        level=level,
        format=_get_format(level),
        colorize=True,
    )

def _get_format(level: str) -> str:
    if level == "DEBUG":
        # 必须包含模块、函数和行号，辅助 agent 定位代码
        return (
            "<cyan>{time:HH:mm:ss}</cyan> | "
            "<level>{level:8}</level> | "
            "<green>{name}:{function}:{line}</green> | "
            "<level>{message}</level>"
        )
    return "<level>{level:8}</level> | <level>{message}</level>"
```

### 2. CLI 集成 (@app.callback)

```python
@app.callback()
def main(
    verbose: Annotated[int, typer.Option("-v", count=True)] = 0,
):
    """Vibe 3.0 - Orchestrator for AI Agents"""
    setup_logging(verbose=verbose)
```

---

## 日志级别定义

| 级别 | 用途 | Agent 消费逻辑 |
|------|------|---------------|
| DEBUG | 代码级调试情况 | 观察 API 调用参数、中间状态 |
| INFO | 核心步骤开始/结束 | 跟踪当前执行到哪个分片 |
| SUCCESS | 目标达成 | 确认任务成功 |
| WARNING | 自动纠偏或环境小问题 | 记录但不阻断流程 |
| ERROR | 执行失败 | 触发异常处理流程 |

---

## 核心要点

✅ **必须实现**：
- Loguru 初始化函数
- CLI `-v` 参数支持
- 控制台格式化输出

⏸️ **暂不实现**（预留接口）：
- JSON 日志格式
- 远程日志收集
- 敏感信息过滤

🎯 **目标**：
- 30 分钟内完成
- 代码 < 100 行
- 支持命令行动态调整日志级别