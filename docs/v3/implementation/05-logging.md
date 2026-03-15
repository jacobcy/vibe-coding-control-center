---
document_type: implementation-guide
title: Vibe 3.0 - Logging System
status: active
author: Claude Sonnet 4.6
created: 2026-03-15
last_updated: 2026-03-15
related_docs:
  - docs/v3/implementation/02-architecture.md
  - docs/v3/implementation/03-coding-standards.md
---

# Vibe 3.0 - 日志系统 (Agent-Centric)

## 设计原则

**Agent 友好优先**：
- ✅ **结构化语义**：通过 `logger.bind()` 赋予日志明确的操作上下文
- ✅ **可追踪性**：强制使用 `logger.exception()` 记录完整错误堆栈
- ✅ **精准定位**：DEBUG 日志必须包含 `文件:行号:函数` 信息
- ✅ **控制台美化**：Rich 集成，提供直观的进度视觉反馈

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

## 最佳实践

- **Lazy Formatting**: 使用 `logger.debug("Processing {}", obj)` 而不是 f-string，性能更佳。
- **No Global Statics**: 日志配置应由 `cli.py` 驱动，不要在模块层直接硬编码。
- **Silent by Default**: 除非 `-v`, 否则不打印多余的 INFO/DEBUG，保持 agent 终端整洁。
setup_logging(level="INFO")

    logger.info("Test message")
    captured = capsys.readouterr()

    assert "Test message" in captured.err

def test_file_logging(tmp_path):
    """测试文件日志"""
    log_file = tmp_path / "test.log"

    setup_logging(level="DEBUG", log_file=log_file)
    logger.info("Test file logging")

    assert log_file.exists()
    assert "Test file logging" in log_file.read_text()

def test_verbose_override():
    """测试 -v 参数优先级"""
    setup_logging(level="ERROR", verbose=2)

    # DEBUG 级别应该生效
    logger.debug("Should be visible")
```

---

## 常见问题

### Q: 为什么用 Loguru 而不是标准 logging？

**Loguru 优势**：
- ✅ 开箱即用，无需配置
- ✅ 自动异常追踪
- ✅ 自动日志轮转
- ✅ 更好的格式化
- ✅ 线程安全

### Q: 日志文件会不会无限增长？

**不会**：
- `rotation="10 MB"`：每 10 MB 轮转一次
- `retention="7 days"`：只保留 7 天
- `compression="zip"`：自动压缩旧日志

### Q: 生产环境推荐什么配置？

```yaml
# ~/.vibe/config.yaml
log_level: INFO
log_file: ~/.vibe/logs/vibe.log
```

使用：
```bash
vibe3 pr draft      # 正常使用
vibe3 pr draft -v   # 需要调试时
```

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