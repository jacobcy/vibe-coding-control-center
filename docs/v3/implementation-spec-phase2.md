# Vibe 3.0 实现规范 - Phase 2

> **目的**: 明确定义实现细节，限制 agent 自由发挥空间
> **强制程度**: 所有 "必须" 条款不得违反

---

## 一、技术栈（强制）

### 必须使用的依赖

| 包名 | 版本要求 | 用途 | 强制程度 |
|------|----------|------|----------|
| typer | ^0.9.0 | CLI 框架 | **必须** |
| rich | ^13.0.0 | 美化输出 | **必须** |
| pydantic | ^2.0.0 | 数据验证 | **必须** |
| loguru | ^0.7.0 | 结构化日志 | **必须** |

### 禁止使用的依赖

- ❌ argparse (用 typer 替代)
- ❌ ORM (SQLAlchemy, peewee)
- ❌ Web 框架 (Django, Flask, FastAPI)
- ❌ print() (用 logger 或 rich)

---

## 二、目录结构（强制）

```
scripts/python/vibe3/
├── __init__.py
├── cli.py                    # Typer 入口 (< 50 行)
├── commands/                 # 命令调度层
│   ├── __init__.py
│   ├── flow.py              # flow 命令 (< 100 行)
│   └── task.py              # task 命令 (< 100 行)
├── services/                 # 业务逻辑层
│   ├── __init__.py
│   ├── flow_service.py      # (< 300 行)
│   └── task_service.py      # (< 300 行)
├── clients/                  # 外部依赖封装
│   ├── __init__.py
│   ├── git_client.py        # Git 操作
│   ├── github_client.py     # GitHub API
│   └── store_client.py      # SQLite 存储
├── models/                   # Pydantic 模型
│   ├── __init__.py
│   ├── flow.py
│   └── task.py
├── ui/                       # Rich 输出
│   ├── __init__.py
│   └── console.py
└── config/
    ├── __init__.py
    └── settings.py
```

---

## 三、分层职责（强制）

### Layer 1: CLI (cli.py)

**代码量**: < 50 行

**职责**:
- 创建 Typer app
- 注册 commands
- **不做任何业务逻辑**

**示例**:
```python
import typer
from commands import flow, task

app = typer.Typer(name="vibe3")
app.add_typer(flow.app, name="flow")
app.add_typer(task.app, name="task")

if __name__ == "__main__":
    app()
```

### Layer 2: Commands (commands/)

**代码量**: 每个文件 < 100 行

**职责**:
- 定义命令和参数
- 参数验证（用 Pydantic）
- 调用 service
- 格式化输出（用 Rich）

**禁止**:
- ❌ 直接调用 subprocess
- ❌ 直接操作数据库
- ❌ 业务逻辑

**示例** (commands/flow.py):
```python
import typer
from typing import Annotated
from services.flow_service import FlowService
from ui.console import console

app = typer.Typer()

@app.command()
def new(
    name: Annotated[str, typer.Argument(help="Flow name")],
    branch: Annotated[str | None, typer.Option(help="Base branch")] = None,
    verbose: Annotated[int, typer.Option("-v", count=True)] = 0,
):
    """Create new flow with dirty workspace check."""
    service = FlowService()
    flow = service.create_flow(name, base_branch=branch)
    console.print(f"[green]✓[/green] Created flow: {flow.slug}")
```

### Layer 3: Services (services/)

**代码量**: 每个文件 < 300 行

**职责**:
- 业务逻辑编排
- 调用多个 client
- 数据转换

**禁止**:
- ❌ 直接 I/O 操作
- ❌ UI 逻辑

**示例** (services/flow_service.py):
```python
from typing import Optional
from clients.git_client import GitClient
from clients.store_client import StoreClient
from models.flow import Flow, FlowCreate

class FlowService:
    def __init__(
        self,
        git: GitClient = GitClient(),
        store: StoreClient = StoreClient(),
    ):
        self.git = git
        self.store = store

    def create_flow(
        self,
        name: str,
        base_branch: Optional[str] = None,
    ) -> Flow:
        """Create new flow with validation."""
        # 1. Check dirty workspace
        if self.git.is_dirty():
            raise DirtyWorkspaceError("Commit or stash changes first")

        # 2. Create branch
        branch = f"task/{name}"
        self.git.create_branch(branch, base_branch)

        # 3. Store flow
        flow = FlowCreate(slug=name, branch=branch)
        return self.store.create_flow(flow)
```

### Layer 4: Clients (clients/)

**允许**: subprocess, 文件 I/O, 数据库操作

**要求**: 提供 Protocol 接口用于 mock

**示例** (clients/git_client.py):
```python
from typing import Protocol
import subprocess

class GitClient(Protocol):
    """Git client protocol for dependency injection."""
    def get_current_branch(self) -> str: ...
    def is_dirty(self) -> bool: ...
    def create_branch(self, name: str, base: str | None) -> None: ...

class GitCLI:
    """Default Git implementation using subprocess."""
    def get_current_branch(self) -> str:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, check=True, text=True
        )
        return result.stdout.strip()

    def is_dirty(self) -> bool:
        result = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True, check=True, text=True
        )
        return bool(result.stdout.strip())
```

### Layer 5: Models (models/)

**要求**: 所有字段必须有类型注解

**示例** (models/flow.py):
```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class FlowBase(BaseModel):
    """Flow base model."""
    slug: str = Field(..., description="Flow identifier")
    branch: str = Field(..., description="Git branch name")

class FlowCreate(FlowBase):
    """Flow creation request."""
    task_issue: Optional[int] = None
    base_branch: Optional[str] = None

class Flow(FlowBase):
    """Flow response model."""
    id: int
    status: str = "active"
    created_at: datetime

    class Config:
        from_attributes = True
```

---

## 四、错误处理（强制）

### 自定义异常

```python
# exceptions.py
class VibeError(Exception):
    """Base exception for Vibe."""
    pass

class DirtyWorkspaceError(VibeError):
    """Workspace has uncommitted changes."""
    pass

class FlowNotFoundError(VibeError):
    """Flow not found in store."""
    pass
```

### 使用示例

```python
# services/flow_service.py
from exceptions import DirtyWorkspaceError, FlowNotFoundError

def create_flow(self, name: str) -> Flow:
    if self.git.is_dirty():
        raise DirtyWorkspaceError("Workspace has uncommitted changes")

    # ...

def get_flow(self, slug: str) -> Flow:
    flow = self.store.get_flow(slug)
    if not flow:
        raise FlowNotFoundError(f"Flow '{slug}' not found")
    return flow
```

---

## 五、日志规范（强制）

### 配置

```python
# config/logging.py
from loguru import logger
import sys

def setup_logging(verbose: int) -> None:
    """Configure loguru based on verbosity level."""
    logger.remove()

    if verbose == 0:
        logger.add(sys.stderr, level="ERROR", format="{message}")
    elif verbose == 1:
        logger.add(sys.stderr, level="INFO", format="<green>{message}</green>")
    else:
        logger.add(
            sys.stderr,
            level="DEBUG",
            format="<cyan>{time:HH:mm:ss}</cyan> | <level>{level:8}</level> | {message}"
        )
```

### 使用

```python
from loguru import logger

# ✅ 正确
logger.info(f"Creating flow: {name}")
logger.success(f"Created flow: {flow.slug}")
logger.error(f"Failed to create flow: {e}")

# ❌ 错误
print(f"Creating flow: {name}")
```

### -v 参数实现（强制）

每个命令必须支持 `-v` 参数：

```python
@app.command()
def new(
    name: str,
    verbose: Annotated[int, typer.Option("-v", count=True)] = 0,
):
    """Create new flow with logging control."""
    setup_logging(verbose)
    logger.info(f"Creating flow: {name}")
    # ...
```

---

## 六、类型注解（强制）

### 要求

1. **所有公共函数必须有类型注解**
2. **使用 Python 3.10+ 类型语法**
3. **禁止使用 `Any` 类型**

### 示例

```python
# ✅ 正确
from typing import Optional
from models.flow import Flow

def get_flow(slug: str) -> Optional[Flow]:
    """Get flow by slug."""
    return self.store.get_flow(slug)

# ❌ 错误
def get_flow(slug):  # 缺少类型注解
    return self.store.get_flow(slug)
```

---

## 七、测试要求（强制）

### 单元测试

每个 service 和 client 必须有单元测试：

```python
# tests/unit/test_flow_service.py
import pytest
from services.flow_service import FlowService
from exceptions import DirtyWorkspaceError

def test_create_flow_with_dirty_workspace():
    """Test that dirty workspace raises error."""
    git_mock = MockGitClient(is_dirty_result=True)
    service = FlowService(git=git_mock)

    with pytest.raises(DirtyWorkspaceError):
        service.create_flow("test-flow")
```

### 契约测试

每个命令必须有契约测试：

```bash
# tests3/flow/contract_tests.sh
test_flow_new() {
    output=$(vibe3 flow new test-flow 2>&1)
    [[ $? -eq 0 ]] || fail "flow new failed"
    pass "flow new creates flow"
}
```

---

## 八、实现检查清单

在提交代码前，必须确认：

- [ ] 所有依赖都符合要求
- [ ] 目录结构符合规范
- [ ] 每层代码量不超标
- [ ] 所有公共函数有类型注解
- [ ] 使用 Typer 而不是 argparse
- [ ] 使用 Rich 而不是 print
- [ ] 使用 Pydantic 模型
- [ ] 使用 loguru 日志
- [ ] 支持 -v 参数
- [ ] 有单元测试
- [ ] 有契约测试
- [ ] 通过 mypy 类型检查
- [ ] 通过 ruff lint 检查
- [ ] 通过 black 格式检查

---

## 九、禁止事项

### 绝对禁止

- ❌ 在 Commands 层直接调用 subprocess
- ❌ 在 Commands 层直接操作数据库
- ❌ 使用 print() 而不是 logger/rich
- ❌ 使用 argparse 而不是 typer
- ❌ 函数超过 100 行
- ❌ 文件超过 300 行（Client 层除外）
- ❌ 缺少类型注解
- ❌ 使用 `Any` 类型
- ❌ 裸 except 捕获所有异常

---

## 十、验收标准

### Phase 2 完成条件

| 标准 | 验证方法 |
|------|----------|
| ✅ 所有命令可用 | 契约测试通过 |
| ✅ 代码符合规范 | mypy + ruff + black 通过 |
| ✅ 测试覆盖充分 | 单元测试 + 契约测试 |
| ✅ 文档完整 | README 更新 |

### 不允许通过的条件

- ❌ 架构不符合规范
- ❌ 缺少类型注解
- ❌ 使用了禁止的依赖
- ❌ 代码量超标
- ❌ 测试不充分

---

**结论**: 本规范为强制要求，agent 必须严格遵守，不得自由发挥。