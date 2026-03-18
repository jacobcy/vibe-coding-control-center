# Observability Module

Vibe 3.0 的可观测性模块，统一管理日志、追踪和审计。

## 目录结构

```
src/vibe3/observability/
├── __init__.py       # 模块入口
├── logger.py         # 结构化日志配置
├── trace.py          # 运行时调用链追踪
└── audit.py          # 审计日志（预留）
```

## 快速开始

### 1. 日志配置

在 CLI 入口点集成日志系统：

```python
import typer
from typing import Annotated
from vibe3.observability import setup_logging

app = typer.Typer()

@app.callback()
def main(
    verbose: Annotated[int, typer.Option("-v", count=True)] = 0,
):
    """Vibe 3.0 CLI"""
    setup_logging(verbose=verbose)
```

**Verbose 级别**：
- `-v` (verbose=1): INFO 级别，显示成功/信息提示
- `-vv` (verbose=2): DEBUG 级别，显示文件:行号:函数信息

### 2. 在代码中使用日志

```python
from loguru import logger

# 绑定语义上下文（Agent 友好）
logger.bind(
    command="pr draft",
    domain="pr",
    action="create_draft"
).info("Creating draft PR")

# 记录错误时保留完整堆栈
try:
    risky_operation()
except Exception as e:
    logger.exception(f"Operation failed: {e}")
    raise
```

### 3. 使用追踪系统

```python
from vibe3.observability import Tracer, TraceContext

# 方式 1: 使用上下文管理器
with TraceContext(command="pr draft", domain="pr"):
    # 执行命令
    pass

# 方式 2: 使用 Tracer API
tracer = Tracer()
span = tracer.trace_call("service.pr.create_draft", args={"title": "Fix"})
span.result = {"pr_number": 123}
```

## 模块职责

### logger.py
- ✅ 日志初始化和配置
- ✅ Verbosity 控制
- ✅ 结构化格式化
- ⏸️ JSON 日志格式（预留）
- ⏸️ 远程日志收集（预留）

### trace.py
- ✅ 调用链追踪
- ✅ `--trace` 参数支持
- ⏸️ 性能监控（预留）
- ⏸️ 状态机转换日志（预留）

### audit.py
- ⏸️ 动作记录（预留）
- ⏸️ 用户身份追踪（预留）
- ⏸️ 资源访问日志（预留）

## 设计原则

**Agent 友好优先**：
- ✅ 结构化语义：通过 `logger.bind()` 赋予日志明确的操作上下文
- ✅ 可追踪性：强制使用 `logger.exception()` 记录完整错误堆栈
- ✅ 精准定位：DEBUG 日志必须包含 `文件:行号:函数` 信息
- ✅ 控制台美化：Rich 集成，提供直观的进度视觉反馈

## 参考文档

- [05-logging.md](../../../docs/v3/infrastructure/05-logging.md) - 日志规范
- [02-architecture.md](../../../docs/v3/infrastructure/02-architecture.md) - 架构设计

---

**维护者**: Vibe Team
**最后更新**: 2026-03-17