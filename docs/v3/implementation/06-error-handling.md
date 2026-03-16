---
document_type: implementation-guide
title: Vibe 3.0 - Error Handling
status: active
author: Claude Sonnet 4.6
created: 2026-03-15
last_updated: 2026-03-16
related_docs:
  - docs/standards/v3/handoff-store-standard.md
  - docs/standards/v3/github-remote-call-standard.md
  - docs/v3/implementation/02-architecture.md
  - docs/v3/implementation/03-coding-standards.md
---

# Vibe 3.0 - 异常处理

## 设计原则

**简单但统一**：
- ✅ 统一的异常基类
- ✅ 区分用户错误和系统错误
- ✅ CLI 层统一捕获和展示
- ❌ 不做复杂的异常层级
- ❌ 不做异常恢复机制

---

## 异常层级（最小化）

```python
# models/exceptions.py
from typing import Optional

class VibeError(Exception):
    """所有 Vibe 异常的基类"""

    def __init__(self, message: str, recoverable: bool = False):
        self.message = message
        self.recoverable = recoverable  # 用户是否可以修正
        super().__init__(message)


# ========== 用户错误（可恢复）==========

class UserError(VibeError):
    """用户输入错误，可通过修正参数解决"""
    recoverable = True


class ValidationError(UserError):
    """参数验证失败"""
    pass


class ConfigError(UserError):
    """配置错误"""
    pass


# ========== 系统错误（不可恢复）==========

class SystemError(VibeError):
    """系统级错误，需要人工介入"""
    recoverable = False


class GitError(SystemError):
    """Git 操作失败"""

    def __init__(self, operation: str, details: str):
        super().__init__(f"Git {operation} failed: {details}")
        self.operation = operation


class GitHubError(SystemError):
    """GitHub API 错误"""

    def __init__(self, status_code: int, message: str):
        super().__init__(f"GitHub API error ({status_code}): {message}")
        self.status_code = status_code


# ========== 业务错误 ==========

class PRNotFoundError(VibeError):
    """PR 不存在"""

    def __init__(self, pr_number: int):
        super().__init__(f"PR #{pr_number} not found", recoverable=False)
        self.pr_number = pr_number


class FlowNotFoundError(VibeError):
    """Flow 不存在"""

    def __init__(self, flow_slug: str):
        super().__init__(f"Flow '{flow_slug}' not found", recoverable=False)
        self.flow_slug = flow_slug
```

---

## 各层异常处理策略

### Layer 1: CLI 层（统一捕获）

```python
# cli.py
import sys
import typer
from loguru import logger
from models.exceptions import VibeError, UserError, SystemError

def main():
    """CLI 入口，统一异常处理"""
    try:
        app()
    except UserError as e:
        # 用户错误：简洁提示
        logger.error(e.message)
        if e.recoverable:
            logger.info("Please check your input and try again")
        sys.exit(1)

    except SystemError as e:
        # 系统错误：显示详情
        logger.exception("System error occurred")
        sys.exit(2)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(130)

    except Exception as e:
        # 未知错误：打印完整栈
        logger.exception("Unexpected error")
        sys.exit(99)

app = typer.Typer(
    name="vibe3",
    help="Vibe 3.0 - AI Development Orchestrator",
    add_completion=False,
)

if __name__ == "__main__":
    main()
```

### Layer 2: Command 层（转换异常）

```python
# commands/pr.py
import typer
from loguru import logger
from services.pr_service import PRService
from models.exceptions import GitHubError, PRNotFoundError

app = typer.Typer()

@app.command()
def show(pr_number: int):
    """Show PR details"""
    try:
        service = PRService()
        pr = service.get_pr(pr_number)
        logger.success(f"PR #{pr.number}: {pr.title}")
    except GitHubError as e:
        if e.status_code == 404:
            raise PRNotFoundError(pr_number) from e
        raise  # 重新抛出，让 CLI 层处理
```

### Layer 3: Service 层（记录日志）

```python
# services/pr_service.py
from loguru import logger
from clients.github_client import GitHubClient
from models.exceptions import GitError, PRNotFoundError

class PRService:
    def __init__(self):
        self.gh = GitHubClient()

    def get_pr(self, pr_number: int):
        """获取 PR 详情"""
        logger.info(f"Fetching PR #{pr_number}")

        try:
            pr = self.gh.get_pr(pr_number)
            logger.debug(f"PR fetched: {pr.title}")
            return pr
        except GitError as e:
            logger.error(f"Failed to fetch PR #{pr_number}: {e}")
            raise
```

### Layer 4: Client 层（抛出具体异常）

```python
# clients/github_client.py
import subprocess
from models.exceptions import GitError, GitHubError
from models.pr import PR

class GitHubClient:
    def get_pr(self, pr_number: int) -> PR:
        """获取 PR（调用 gh CLI）"""
        result = subprocess.run(
            ["gh", "pr", "view", str(pr_number), "--json"],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            if "404" in result.stderr:
                raise GitHubError(404, f"PR #{pr_number} not found")
            raise GitError("view PR", result.stderr)

        return PR.parse_raw(result.stdout)
```

---

## 错误消息规范

### 用户错误（简洁）

```python
# ✅ 正确：简洁提示
raise ValidationError("PR number must be positive integer")

# 输出：
# ERROR: PR number must be positive integer
# Please check your input and try again
```

### 系统错误（详细）

```python
# ✅ 正确：包含上下文
raise GitError("create PR", "authentication failed")

# 输出：
# ERROR: Git create PR failed: authentication failed
# System error occurred
# [完整错误栈]
```

### 业务错误（友好）

```python
# ✅ 正确：清晰说明
raise PRNotFoundError(123)

# 输出：
# ERROR: PR #123 not found
```

---

## 实现步骤

### Step 1: 创建异常模块

```bash
mkdir -p scripts/python/vibe3/models
touch scripts/python/vibe3/models/__init__.py
touch scripts/python/vibe3/models/exceptions.py
```

### Step 2: 实现异常定义

创建文件 [models/exceptions.py](scripts/python/vibe3/models/exceptions.py)：

```python
# 复制上面的异常定义即可
```

### Step 3: 在 CLI 层添加异常处理

编辑 [cli.py](scripts/python/vibe3/cli.py)：

```python
# 添加 main() 函数的异常处理逻辑
```

---

## 预留的扩展点

### 1. 异常恢复（将来）

```python
# 预留接口，现在不实现
class RecoverableError(VibeError):
    """可恢复的错误"""

    def suggest_fix(self) -> list[str]:
        """建议的修复方案"""
        # TODO: 将来可以提供智能修复建议
        return []
```

### 2. 异常链追踪（将来）

```python
# 预留字段，现在不实现
class VibeError(Exception):
    def __init__(self, message: str, context: dict | None = None):
        self.context = context or {}  # 预留上下文字段
        super().__init__(message)
```

---

## 测试示例

```python
# tests/test_exceptions.py
import pytest
from models.exceptions import VibeError, UserError, PRNotFoundError

def test_user_error_recoverable():
    """测试用户错误可恢复"""
    error = UserError("test")
    assert error.recoverable is True

def test_pr_not_found_error():
    """测试 PR 不存在错误"""
    error = PRNotFoundError(123)
    assert error.pr_number == 123
    assert "123" in error.message

def test_exception_chain():
    """测试异常链"""
    with pytest.raises(PRNotFoundError):
        try:
            raise ValueError("original error")
        except ValueError as e:
            raise PRNotFoundError(123) from e
```

---

## 常见问题

### Q: 为什么不使用 Python 内置异常？

```python
# ❌ 不推荐：使用内置异常
raise ValueError("Invalid PR number")

# ✅ 推荐：使用自定义异常
raise ValidationError("Invalid PR number")
```

**原因**：
- 自定义异常可以统一捕获 `VibeError`
- 可以区分用户错误和系统错误
- 可以添加额外字段（如 `recoverable`）

### Q: 什么时候用哪种异常？

| 场景 | 异常类型 |
|------|----------|
| 用户输入错误参数 | `ValidationError` |
| 配置文件格式错误 | `ConfigError` |
| Git 命令失败 | `GitError` |
| GitHub API 调用失败 | `GitHubError` |
| PR/Flow 不存在 | `PRNotFoundError` / `FlowNotFoundError` |

---

## 核心要点

✅ **必须实现**：
- 统一的异常基类 `VibeError`
- CLI 层统一异常处理
- 区分 `UserError` 和 `SystemError`

⏸️ **暂不实现**（预留接口）：
- 异常恢复机制
- 智能修复建议
- 复杂的异常追踪

🎯 **目标**：
- 30 分钟内完成
- 代码 < 150 行
- 覆盖 90% 常见错误场景