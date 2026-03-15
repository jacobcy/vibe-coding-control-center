---
document_type: implementation-guide
title: Vibe 3.0 - Coding Standards
status: active
author: Claude Sonnet 4.6
created: 2026-03-15
last_updated: 2026-03-15
related_docs:
  - docs/v3/implementation/02-architecture.md
  - .agent/rules/python-standards.md
---

# Vibe 3.0 - 编码标准

本文档定义 Vibe 3.0 的编码标准，包括代码风格、复杂度控制、最佳实践等。

详细标准见 **[.agent/rules/python-standards.md](../../../.agent/rules/python-standards.md)**

---

## 技术栈（强制）

### 必须使用的依赖

| 包名 | 版本要求 | 用途 | 强制程度 |
|------|----------|------|----------|
| typer | ^0.9.0 | CLI 框架 | **必须** |
| rich | ^13.0.0 | 美化输出 | **必须** |
| pydantic | ^2.0.0 | 数据验证 | **必须** |
| loguru | ^0.7.0 | 结构化日志 | **必须** |

### 禁止使用的依赖

- ❌ **argparse** (用 typer 替代)
- ❌ **ORM** (SQLAlchemy, peewee)
- ❌ **Web 框架** (Django, Flask, FastAPI)
- ❌ **print()** (用 logger 或 rich)

---

## 类型注解（强制）

### 要求

1. **所有公共函数必须有类型注解**
2. **使用 Python 3.10+ 类型语法**
3. **禁止使用 `Any` 类型**

### 示例

```python
# ✅ 正确
from models.pr import PRRequest, PRResponse

def create_pr(request: PRRequest) -> PRResponse:
    """Create PR with full type safety."""
    ...

# ❌ 错误
def create_pr(request):  # 缺少类型注解
    ...

# ❌ 错误
from typing import Any
def create_pr(request: Any) -> Any:  # 使用 Any
    ...
```

---

## 代码复杂度（强制）

### 代码规模限制

为保持代码可理解性，必须遵守以下文件和函数规模限制：

| 层级 | 文件最大行数 | 函数最大行数 | 理由 |
|------|------------|------------|------|
| CLI (cli.py) | < 50 行 | < 20 行 | 只做转发 |
| Commands | < 100 行 | < 50 行 | 参数验证 + 调用 |
| Services | < 300 行 | < 100 行 | 业务逻辑 |
| Clients | 无限制 | < 150 行 | 封装复杂度 |

### 复杂度限制

- **禁止**：嵌套超过 3 层
- **禁止**：单个函数超过 10 个参数
- **禁止**：循环复杂度 > 10

### 重构建议

```python
# ❌ 错误：嵌套太深
def process_pr(pr):
    if pr.state == "open":
        if pr.draft:
            if pr.author == "me":
                # 逻辑太深
                ...

# ✅ 正确：提前返回
def process_pr(pr):
    if pr.state != "open":
        return
    if not pr.draft:
        return
    if pr.author != "me":
        return
    # 逻辑清晰
    ...
```

---

## 导入顺序（强制）

```python
# 1. 标准库
import os
import sys
from pathlib import Path
from typing import Literal

# 2. 第三方库
import typer
from loguru import logger
from pydantic import BaseModel

# 3. 本地模块
from vibe3.clients.git import GitClient
from vibe3.models.pr import PRRequest
```

---

## 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 模块 | snake_case | `pr_service.py` |
| 类 | PascalCase | `PRService` |
| 函数 | snake_case | `create_pr()` |
| 常量 | UPPER_SNAKE_CASE | `DEFAULT_REMOTE` |
| 私有函数 | _snake_case | `_validate_input()` |

---

## 错误处理（强制）

### 禁止裸 except

```python
# ❌ 错误：裸 except
try:
    result = risky_operation()
except:
    return None

# ✅ 正确：捕获具体异常
try:
    result = risky_operation()
except ValueError as e:
    logger.error(f"Value error: {e}")
    raise
except NetworkError as e:
    logger.error(f"Network error: {e}")
    raise
```

### 异常链

```python
# ✅ 正确：使用异常链
try:
    result = subprocess.run(cmd)
except subprocess.CalledProcessError as e:
    raise GitError("create PR", str(e)) from e
```

---

## 日志规范（强制）

详见：**[05-logging.md](05-logging.md)** (Agent-Centric Logging Standard)

---

## 性能优化

### 避免常见陷阱

```python
# ✅ 正确：使用 lazy formatting
logger.debug("Processing item {}", item_id)

# ❌ 错误：立即格式化
logger.debug(f"Processing item {item_id}")

# ✅ 正确：使用 join 连接字符串
result = "".join(items)

# ❌ 错误：循环拼接字符串
result = ""
for item in items:
    result += item
```

---

## 测试要求

### 测试覆盖率

- **最低要求**：80% 代码覆盖率
- **核心路径**：100% 覆盖

### 测试结构

```
tests/
├── test_config/
│   └── test_settings.py
├── test_services/
│   ├── test_pr_service.py
│   ├── test_flow_service.py
│   └── test_task_service.py
├── test_clients/
│   ├── test_git_client.py
│   └── test_github_client.py
└── test_commands/
    ├── test_pr.py
    ├── test_flow.py
    └── test_task.py
```

---

## 代码审查检查清单

### 类型安全

- [ ] 所有公共函数有类型注解
- [ ] 不使用 `Any` 类型
- [ ] mypy 检查通过

### 代码质量

- [ ] 函数不超过最大行数
- [ ] 嵌套不超过 3 层
- [ ] 不使用裸 `except`

### 测试

- [ ] 核心路径有测试
- [ ] 测试覆盖率 >= 80%
- [ ] 异常场景有测试

### 日志

- [ ] 不使用 `print`
- [ ] 关键操作有日志
- [ ] 错误日志包含上下文

---

## 工具配置

### pyproject.toml

```toml
[tool.mypy]
python_version = "3.10"
strict = true
warn_return_any = true
warn_unused_ignores = true

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.black]
line-length = 100
target-version = ["py310"]
```

---

## 参考文档

- **[.agent/rules/python-standards.md](../../../.agent/rules/python-standards.md)** - 完整 Python 标准
- **[02-architecture.md](02-architecture.md)** - 架构设计
- **[06-error-handling.md](06-error-handling.md)** - 异常处理

---

**维护者**：Vibe Team
**最后更新**：2026-03-15
