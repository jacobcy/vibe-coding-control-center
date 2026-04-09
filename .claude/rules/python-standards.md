---
document_type: standard
title: Python Standards (Vibe 3.0)
status: active
scope: python-implementation
author: Claude Sonnet 4.6
created: 2026-03-15
last_updated: 2026-03-15
related_docs:
  - docs/v3/infrastructure/02-architecture.md
  - docs/v3/infrastructure/03-coding-standards.md
  - docs/standards/glossary.md
  - SOUL.md
  - CLAUDE.md
---

# Python Standards (Vibe 3.0)

本文件定义 Vibe 3.0 Python 实现的标准，包括代码风格、架构规范、依赖管理、测试要求等。

术语以 [docs/standards/glossary.md](../../docs/standards/glossary.md) 为准，动作词以 [docs/standards/action-verbs.md](../../docs/standards/action-verbs.md) 为准。

治理级总原则见 [SOUL.md](../../SOUL.md)，项目上下文与最小硬规则见 [CLAUDE.md](../../CLAUDE.md)。

---

## 版本与依赖

### Python 版本
- **最低版本**：Python 3.12+
- **类型语法**：使用 Python 3.12+ 类型语法（`str | None` 而非 `Optional[str]`）

### 依赖管理（强制）

**本项目使用 uv 管理依赖和虚拟环境**：
- **配置文件**：`pyproject.toml`（项目根目录）
- **安装依赖**：`uv sync`
- **添加依赖**：`uv add <package>`
- **移除依赖**：`uv remove <package>`
- **运行命令**：`uv run <command>`
- **运行 Python**：`uv run python`（**禁止直接使用 `python` 或 `python3`**）

**禁止**：
- ❌ 使用 `python`、`python3`、`pip`、`pip3` 等命令
- ❌ 手动创建虚拟环境（`python -m venv`）
- ❌ 使用 `requirements.txt`（统一用 `pyproject.toml`）

**正确示例**：
```bash
# ✅ 运行 Python 脚本
uv run python src/vibe3/cli.py

# ✅ 运行测试
uv run pytest

# ✅ 运行 mypy
uv run mypy src/vibe3

# ❌ 错误：直接使用 python
python src/vibe3/cli.py

# ❌ 错误：使用 pip
pip install requests
```

### 核心依赖（必须）

| 包名 | 版本 | 用途 | 强制程度 |
|------|------|------|----------|
| typer | ^0.9.0 | CLI 框架 | **必须** |
| rich | ^13.0.0 | 美化输出 | **必须** |
| pydantic | ^2.0.0 | 数据验证 | **必须** |
| pydantic-settings | ^2.0.0 | 配置管理 | **必须** |
| loguru | ^0.7.0 | 结构化日志 | **必须** |

### 可选依赖

| 包名 | 版本 | 用途 | 强制程度 |
|------|------|------|----------|
| pyyaml | ^6.0.0 | YAML 配置 | 可选 |

### 开发依赖（必须）

| 包名 | 版本 | 用途 | 强制程度 |
|------|------|------|----------|
| mypy | ^1.5.0 | 类型检查 | **必须** |
| pytest | ^7.4.0 | 测试框架 | **必须** |
| ruff | ^0.1.0 | Linting | **必须** |
| black | ^23.0.0 | 代码格式化 | **必须** |

### 禁止的依赖

- ❌ 数据库 ORM (SQLAlchemy, peewee)
- ❌ 复杂 API SDK
- ❌ 不需要的框架 (Django, Flask, FastAPI)
- ❌ 分布式系统库

---

## 代码风格

### 类型注解（强制）

**要求**：
1. 所有公共函数必须有类型注解
2. 使用 Python 3.12+ 类型语法
3. 禁止使用 `Any` 类型

**示例**：

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

### 导入顺序（强制）

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

### 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 模块 | snake_case | `pr_service.py` |
| 类 | PascalCase | `PRService` |
| 函数 | snake_case | `create_pr()` |
| 常量 | UPPER_SNAKE_CASE | `DEFAULT_REMOTE` |
| 私有函数 | _snake_case | `_validate_input()` |

---

## 架构分层

### 目录结构（强制）

```
src/vibe3/
├── cli.py                    # Typer 入口
├── commands/                 # 命令调度层（薄层）
│   ├── pr.py                # PR 命令
│   ├── flow.py              # Flow 命令
│   └── task.py              # Task 命令
├── services/                 # 业务逻辑层
│   ├── pr_service.py
│   ├── flow_service.py
│   └── task_service.py
├── clients/                  # 外部依赖封装
│   ├── git_client.py
│   ├── github_client.py
│   └── store_client.py
├── models/                   # Pydantic 数据模型
│   ├── exceptions.py        # 异常定义
│   ├── pr.py
│   ├── flow.py
│   └── task.py
├── ui/                       # 展示层
│   └── console.py
└── config/                   # 配置模块
    ├── settings.py
    └── logging.py
```

### 分层职责（强制）

#### Layer 1: CLI (cli.py)
- **职责**：解析命令行参数，调用 commands
- **代码量**：< 50 行
- **禁止**：业务逻辑、直接 I/O

#### Layer 2: Commands (commands/)
- **职责**：参数验证，调用 service，格式化输出
- **代码量**：每个文件 < 100 行
- **禁止**：直接调用 subprocess、数据库操作

#### Layer 3: Services (services/)
- **职责**：业务逻辑编排
- **代码量**：每个文件 < 300 行
- **禁止**：直接 I/O、UI 逻辑

#### Layer 4: Clients (clients/)
- **职责**：封装外部依赖（Git, GitHub, SQLite）
- **允许**：subprocess、文件 I/O、数据库操作
- **必须**：提供接口用于 mock

#### Layer 5: Models (models/)
- **职责**：Pydantic 数据模型
- **要求**：所有字段必须有类型注解

#### Layer 6: UI (ui/)
- **职责**：Rich 输出格式化
- **禁止**：业务逻辑

### 依赖方向（强制）

```
CLI → Commands → Services → Clients → Models
                ↓
                UI
```

**禁止反向依赖**：
- ❌ Clients 不能调用 Services
- ❌ Services 不能调用 Commands
- ❌ Models 不能调用任何层

---

## 函数大小限制（强制）

| 层级 | 最大行数 | 理由 |
|------|---------|------|
| CLI | < 20 行 | 只做转发 |
| Command | < 50 行 | 参数验证 + 调用 |
| Service | < 100 行 | 业务逻辑 |
| Client | 无限制 | 封装复杂度 |

---

## 代码复杂度（强制）

- **禁止**：嵌套超过 3 层
- **禁止**：单个函数超过 10 个参数
- **禁止**：循环复杂度 > 10

---

## 错误处理（强制）

### 异常层级

```python
# models/exceptions.py

class VibeError(Exception):
    """所有 Vibe 异常的基类"""
    def __init__(self, message: str, recoverable: bool = False):
        self.message = message
        self.recoverable = recoverable
        super().__init__(message)

class UserError(VibeError):
    """用户输入错误，可修正"""
    recoverable = True

class SystemError(VibeError):
    """系统级错误，需要人工介入"""
    recoverable = False
```

### 异常处理策略

**CLI 层**：统一捕获所有异常

```python
def main():
    try:
        app()
    except UserError as e:
        logger.error(e.message)
        sys.exit(1)
    except SystemError as e:
        logger.exception("System error occurred")
        sys.exit(2)
```

**Service 层**：记录错误日志，抛出业务异常

```python
def create_pr(request: PRRequest) -> PR:
    try:
        return self.git_client.create_pr(request)
    except GitError as e:
        logger.error(f"Git operation failed: {e}")
        raise PRCreationError(...) from e
```

**禁止**：
- ❌ 裸 `except:` 捕获所有异常
- ❌ 吞没异常（`except: pass`）
- ❌ 返回 None 表示错误

---

## 日志规范（强制）

### 使用 Loguru

```python
from loguru import logger

# ✅ 正确：结构化日志
logger.info(f"Creating PR for branch {branch}")
logger.success(f"Created PR #{pr_number}")
logger.error(f"Failed to create PR: {e}")

# ❌ 错误：print
print(f"Creating PR for branch {branch}")
```

### 日志级别

| 级别 | 使用场景 |
|------|----------|
| TRACE | 详细的函数调用栈（仅 DEBUG 模式） |
| DEBUG | 开发调试信息 |
| INFO | 正常业务流程 |
| SUCCESS | 操作成功（Loguru 特有） |
| WARNING | 可恢复的异常情况 |
| ERROR | 错误但程序可继续 |
| CRITICAL | 严重错误，程序即将退出 |

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

### 测试规范

```python
import pytest
from services.pr_service import PRService
from models.exceptions import PRNotFoundError

def test_create_pr_success():
    """测试创建 PR 成功"""
    service = PRService()
    pr = service.create_pr(title="Test PR")
    assert pr.title == "Test PR"

def test_create_pr_not_found():
    """测试 PR 不存在"""
    service = PRService()
    with pytest.raises(PRNotFoundError):
        service.get_pr(999)
```

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

## 文档要求

### 函数文档

```python
def create_pr(title: str, body: str | None = None) -> PR:
    """
    创建 Pull Request

    Args:
        title: PR 标题
        body: PR 正文（可选）

    Returns:
        创建的 PR 对象

    Raises:
        PRCreationError: 创建失败时抛出
    """
    ...
```

### 模块文档

```python
"""
PR Service - Pull Request 业务逻辑

本模块负责 PR 创建、更新、合并等业务逻辑。
"""
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

### 文档

- [ ] 公共函数有 docstring
- [ ] 复杂逻辑有注释
- [ ] 模块有文档说明

---

## 工具配置

### pyproject.toml

```toml
[project]
name = "vibe3"
version = "3.0.0"
requires-python = ">=3.10"

[tool.mypy]
python_version = "3.10"
strict = true
warn_return_any = true
warn_unused_ignores = true

[tool.ruff]
line-length = 88
target-version = "py310"

[tool.black]
line-length = 88
target-version = ["py310"]
```

---

## 参考文档

- **[docs/v3/infrastructure/](../../docs/v3/infrastructure/README.md)** - 实施指南
- **[SOUL.md](../../SOUL.md)** - 项目宪法
- **[CLAUDE.md](../../CLAUDE.md)** - 项目上下文

---

## 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 1.0 | 2026-03-15 | 初始版本，定义 Python 标准基础 |

---

**维护者**：Vibe Team
**最后更新**：2026-03-15