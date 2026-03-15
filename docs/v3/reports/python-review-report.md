# Python Code Review Report - Vibe 3.0

**Review Date**: 2026-03-15
**Reviewer**: Claude Sonnet 4.6 (python-reviewer agent)
**Scope**: Phase 3 PR Domain Implementation

---

## Executive Summary

**Overall Status**: ⚠️ **WARNING - Needs Refactoring**

当前实现功能完整，但存在架构问题。Manager 类过于臃肿，违反单一职责原则，缺少现代 Python 工具链支持。

### Critical Metrics

| Metric | Value | Status |
|--------|-------|--------|
| PRManager lines | 563 | ❌ Too large |
| PRManager methods | 11 | ⚠️ Borderline |
| Type hints coverage | ~10% | ❌ Very low |
| Modern tools usage | 0 | ❌ None |
| Test coverage | 7/7 contract tests | ✅ Good |

---

## Files Reviewed

- `scripts/python/pr/manager.py` (563 lines)
- `scripts/python/vibe_core.py` (240 lines)
- `scripts/python/lib/store.py`
- `scripts/python/lib/github.py`

---

## Issues Found

### [CRITICAL] Manager Class Too Heavy - Violates SRP

**File**: `scripts/python/pr/manager.py`
**Lines**: 563
**Issue**: PRManager 承担了太多职责，违反单一职责原则 (Single Responsibility Principle)

**Current Structure**:
```python
class PRManager:
    def __init__(...)
    def _get_current_branch(...)      # Git 操作
    def _build_pr_body(...)            # 文本生成
    def draft(...)                      # PR 创建
    def show(...)                       # PR 展示
    def _infer_group_from_issue(...)   # 业务逻辑
    def ready(...)                      # 发布门控
    def _build_review_body(...)        # 文本生成
    def review(...)                     # 代码审查
    def _perform_basic_review(...)     # 审查逻辑
    def merge(...)                      # PR 合并
```

**Problems**:
1. 混合了 **调度层** 和 **业务逻辑**
2. 直接调用 `subprocess` 和 `gh` 命令
3. 包含文本生成、业务规则、Git 操作等多种职责
4. 难以测试、难以扩展、难以维护

**OpenAI Suggestion** (参考):
```
flowctl/
  commands/
    pr.py          # CLI 调度层
  model/
    pr.py          # 数据模型
  gh/
    gh_wrapper.py  # GitHub 操作
  ui/
    table.py       # 展示逻辑
```

**Recommended Refactoring**:

```python
# pr/manager.py - 只做调度层
class PRManager:
    """PR command dispatcher - thin orchestration layer."""

    def __init__(self):
        self.gh = GitHubClient()
        self.store = FlowStore()
        self.ui = RichUI()

    def draft(self, title: str | None, body: str | None) -> int:
        """Dispatch PR draft creation."""
        # 1. 获取数据
        branch = GitHelper.get_current_branch()
        state = self.store.get_flow_state(branch)

        # 2. 委托给专门的类
        pr_body = PRBodyBuilder.build(state, branch)
        pr_number = self.gh.create_draft_pr(title, pr_body)

        # 3. 更新状态
        self.store.update_pr_number(branch, pr_number)

        # 4. UI 反馈
        self.ui.success(f"Created PR #{pr_number}")
        return pr_number
```

```python
# pr/body_builder.py - 专门的文本生成
class PRBodyBuilder:
    """Build PR body with metadata."""

    @staticmethod
    def build(state: FlowState, branch: str) -> str:
        """Generate PR body from flow state."""
        sections = [
            PRBodyBuilder._build_summary(),
            PRBodyBuilder._build_metadata(state, branch),
            PRBodyBuilder._build_links(state),
        ]
        return "\n".join(sections)
```

```python
# gh/client.py - GitHub 操作封装
class GitHubClient:
    """GitHub CLI wrapper."""

    def create_draft_pr(self, title: str, body: str) -> int:
        """Create draft PR via gh CLI."""
        result = subprocess.run(
            ["gh", "pr", "create", "--draft", "--title", title, "--body", body],
            capture_output=True,
            check=True
        )
        return self._parse_pr_number(result.stdout)
```

**Impact**:
- ✅ 符合 Python 最佳实践
- ✅ 易于测试（每个类可独立测试）
- ✅ 易于扩展（新增功能不影响其他部分）
- ✅ 符合 OpenAI 建议

---

### [HIGH] Missing Modern Python Toolchain

**Issue**: 未使用现代 Python 工具，代码质量和开发效率受限

**Current Stack**:
- ❌ `argparse` - 手动解析参数
- ❌ `print()` - 无结构化日志
- ❌ 无类型验证
- ❌ 无配置管理

**Recommended Stack** (基于 OpenAI 建议):

#### 1. **Typer** - 现代 CLI 框架

**Before** (argparse):
```python
parser = argparse.ArgumentParser(prog="vibe3 pr")
parser.add_argument("--json", action="store_true")
parser.add_argument("-y", "--yes", action="store_true")
subparsers = parser.add_subparsers(dest="sub")

draft_parser = subparsers.add_parser("draft")
draft_parser.add_argument("--title")
draft_parser.add_argument("--body")
# ... 50+ lines of argparse boilerplate
```

**After** (Typer):
```python
import typer
from typing import Annotated

app = typer.Typer()

@app.command()
def draft(
    title: Annotated[str | None, typer.Option(help="PR title")] = None,
    body: Annotated[str | None, typer.Option(help="PR body")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="JSON output")] = False,
    auto_confirm: Annotated[bool, typer.Option("-y", "--yes")] = False,
):
    """Create draft PR with metadata injection."""
    manager = PRManager(json_output=json_output, auto_confirm=auto_confirm)
    manager.draft(title, body)

@app.command()
def show():
    """Show PR details and metadata."""
    PRManager().show()

# 自动生成帮助、参数验证、类型转换
```

**Benefits**:
- ✅ 自动生成帮助文档
- ✅ 自动参数验证
- ✅ 类型提示支持
- ✅ 代码量减少 70%

#### 2. **Rich** - 美化输出

**Before**:
```python
print(f"{'='*60}")
print(f"PR #{pr['number']}: {pr['title']}")
print(f"{'='*60}")
print(f"State: {pr['state']} {'(Draft)' if pr['isDraft'] else '(Ready)'}")
```

**After** (Rich):
```python
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

# 美化的 PR 展示
console.print(Panel(
    f"[bold]PR #{pr['number']}[/bold]: {pr['title']}",
    title="Pull Request",
    border_style="blue"
))

# 表格展示
table = Table(title="Flow Metadata")
table.add_column("Field", style="cyan")
table.add_column("Value", style="green")
table.add_row("Task ID", state.get('flow_slug', 'N/A'))
table.add_row("Flow", state.get('flow_slug', 'N/A'))
console.print(table)
```

#### 3. **Pydantic** - 数据验证

**Before**:
```python
def ready(self, group=None, bump=None):
    # 手动验证
    if group and group not in ['feature', 'bug', 'docs', 'chore']:
        print("Invalid group")
        return
```

**After** (Pydantic):
```python
from pydantic import BaseModel, validator
from enum import Enum

class GroupType(str, Enum):
    FEATURE = "feature"
    BUG = "bug"
    DOCS = "docs"
    CHORE = "chore"

class ReadyRequest(BaseModel):
    group: GroupType | None = None
    bump: bool | None = None

    @validator('bump', always=True)
    def infer_bump(cls, v, values):
        """Auto-infer bump from group."""
        if v is None and 'group' in values:
            return values['group'] == GroupType.FEATURE
        return v

# 使用
request = ReadyRequest(group="feature")  # 自动验证
print(request.bump)  # True (自动推断)
```

#### 4. **Loguru** - 结构化日志

**Before**:
```python
print(f"Creating Draft PR: {title}")
print(f"✓ Created Draft PR: {pr_url}")
print(f"Error creating PR: {e}")
```

**After** (Loguru):
```python
from loguru import logger

# 配置日志级别
logger.add("vibe.log", rotation="10 MB", level="DEBUG")

# 使用
logger.info(f"Creating draft PR: {title}")
logger.success(f"Created PR #{pr_number}: {pr_url}")
logger.error(f"Failed to create PR: {e}")
logger.debug(f"PR body: {body[:100]}...")

# 支持 -v 参数控制
# vibe3 pr draft -v      # INFO level
# vibe3 pr draft -vv     # DEBUG level
```

**Implementation**:
```python
import typer
from loguru import logger

app = typer.Typer()

@app.command()
def draft(
    title: str | None = None,
    body: str | None = None,
    verbose: Annotated[int, typer.Option("-v", "--verbose", count=True)] = 0,
):
    """Create draft PR with logging control."""
    # 配置日志级别
    if verbose == 0:
        logger.remove()  # 只显示 ERROR
    elif verbose == 1:
        logger.remove()
        logger.add(sys.stderr, level="INFO")  # INFO
    else:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")  # DEBUG

    logger.info("Starting PR draft creation")
    # ...
```

---

### [HIGH] Missing Type Hints

**Issue**: 代码缺少类型注解，违反 Python 最佳实践

**Current Coverage**: ~10%

**Before**:
```python
def _build_pr_body(self, state, branch):
    """Build PR body with metadata injection."""
    body_parts = []
    # ...
    return ''.join(body_parts)

def draft(self, title=None, body=None):
    branch = self._get_current_branch()
    # ...
    return pr_number
```

**After** (完整类型注解):
```python
from typing import Optional
from dataclasses import dataclass

@dataclass
class FlowState:
    """Flow state data model."""
    flow_slug: str
    task_issue_number: Optional[int] = None
    pr_number: Optional[int] = None
    planner_actor: Optional[str] = None
    executor_actor: Optional[str] = None
    spec_ref: Optional[str] = None

    class Config:
        extra = "allow"  # 允许额外字段

def _build_pr_body(self, state: FlowState, branch: str) -> str:
    """Build PR body with metadata injection."""
    body_parts: list[str] = []
    # ...
    return ''.join(body_parts)

def draft(
    self,
    title: Optional[str] = None,
    body: Optional[str] = None
) -> Optional[int]:
    """Create draft PR and return PR number."""
    branch: str = self._get_current_branch()
    # ...
    return pr_number
```

**Benefits**:
- ✅ IDE 自动补全
- ✅ 静态类型检查 (mypy)
- ✅ 更好的文档
- ✅ 减少运行时错误

---

### [MEDIUM] Direct Subprocess Calls

**Issue**: 直接调用 `subprocess` 和 `gh` 命令，难以测试和 mock

**Before**:
```python
def _get_current_branch(self):
    return subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).decode().strip()

def draft(self, title=None, body=None):
    cmd = ["gh", "pr", "create", "--draft", "--title", title, "--body", body]
    output = subprocess.check_output(cmd).decode().strip()
```

**After** (依赖注入):
```python
from typing import Protocol

class GitClient(Protocol):
    """Git client protocol for dependency injection."""
    def get_current_branch(self) -> str: ...
    def get_diff(self, base: str) -> str: ...

class GitHubClient(Protocol):
    """GitHub client protocol for dependency injection."""
    def create_pr(self, title: str, body: str, draft: bool) -> int: ...
    def get_pr(self, number: int) -> dict: ...

class PRManager:
    def __init__(
        self,
        git: GitClient = GitCLI(),  # 默认实现
        gh: GitHubClient = GitHubCLI(),  # 默认实现
    ):
        self.git = git
        self.gh = gh

    def draft(self, title: str | None, body: str | None) -> int | None:
        branch = self.git.get_current_branch()
        pr_number = self.gh.create_pr(title, body, draft=True)
        return pr_number

# 测试时可以注入 mock
class MockGitClient:
    def get_current_branch(self) -> str:
        return "test-branch"

manager = PRManager(git=MockGitClient())
```

---

### [MEDIUM] Missing -v Parameter

**Issue**: 缺少日志级别控制参数

**OpenAI Suggestion**:
> 支持 -v 参数控制日志输出

**Implementation**:
```python
import typer
from loguru import logger
from typing import Annotated

@app.command()
def draft(
    title: Annotated[str | None, typer.Option(help="PR title")] = None,
    body: Annotated[str | None, typer.Option(help="PR body")] = None,
    verbose: Annotated[int, typer.Option("-v", "--verbose", count=True)] = 0,
):
    """Create draft PR with configurable logging."""
    # 配置日志
    _setup_logging(verbose)

    logger.info("Creating draft PR")
    # ...

def _setup_logging(verbose: int) -> None:
    """Configure loguru based on verbosity level."""
    logger.remove()  # 移除默认 handler

    if verbose == 0:
        # 只显示 ERROR
        logger.add(sys.stderr, level="ERROR", format="{message}")
    elif verbose == 1:
        # INFO level
        logger.add(sys.stderr, level="INFO", format="<green>{message}</green>")
    elif verbose >= 2:
        # DEBUG level with full context
        logger.add(
            sys.stderr,
            level="DEBUG",
            format="<cyan>{time:HH:mm:ss}</cyan> | <level>{level:8}</level> | {message}"
        )
```

**Usage**:
```bash
vibe3 pr draft                    # ERROR only
vibe3 pr draft -v                 # INFO level
vibe3 pr draft -vv                # DEBUG level
vibe3 pr draft --verbose --verbose  # DEBUG level (alternative)
```

---

## Recommended Architecture

基于 OpenAI 建议和 Python 最佳实践，推荐以下架构：

```
scripts/python/
├── cli.py                    # Typer CLI 入口
├── commands/                 # 命令调度层
│   ├── __init__.py
│   ├── pr.py                # PR 命令调度
│   ├── flow.py              # Flow 命令调度
│   └── task.py              # Task 命令调度
├── models/                   # Pydantic 数据模型
│   ├── __init__.py
│   ├── pr.py                # PR 数据模型
│   ├── flow.py              # Flow 数据模型
│   └── config.py            # 配置模型
├── services/                 # 业务逻辑层
│   ├── __init__.py
│   ├── pr_service.py        # PR 业务逻辑
│   ├── review_service.py    # 审查逻辑
│   └── publish_gate.py      # 发布门控
├── clients/                  # 外部依赖封装
│   ├── __init__.py
│   ├── git_client.py        # Git 操作
│   ├── github_client.py     # GitHub API
│   └── store_client.py      # SQLite 存储
├── ui/                       # 展示层
│   ├── __init__.py
│   ├── console.py           # Rich console
│   └── tables.py            # 表格展示
└── config/                   # 配置管理
    ├── __init__.py
    └── settings.py          # Pydantic Settings
```

### Example Refactored Code

**cli.py** - Typer 入口:
```python
import typer
from commands import pr, flow, task

app = typer.Typer(
    name="vibe3",
    help="Vibe 3.0 - GitHub workflow wrapper CLI"
)

app.add_typer(pr.app, name="pr")
app.add_typer(flow.app, name="flow")
app.add_typer(task.app, name="task")

if __name__ == "__main__":
    app()
```

**commands/pr.py** - 调度层:
```python
import typer
from typing import Annotated
from services.pr_service import PRService
from ui.console import console

app = typer.Typer(help="PR management commands")

@app.command()
def draft(
    title: Annotated[str | None, typer.Option(help="PR title")] = None,
    body: Annotated[str | None, typer.Option(help="PR body")] = None,
    verbose: Annotated[int, typer.Option("-v", count=True)] = 0,
):
    """Create draft PR with metadata injection."""
    service = PRService()
    pr_number = service.create_draft(title, body)

    console.print(f"[green]✓[/green] Created PR #{pr_number}")
    return pr_number
```

**services/pr_service.py** - 业务逻辑:
```python
from typing import Optional
from clients.git_client import GitClient
from clients.github_client import GitHubClient
from clients.store_client import StoreClient
from models.pr import PRRequest, PRResponse

class PRService:
    """PR business logic service."""

    def __init__(
        self,
        git: GitClient = GitClient(),
        gh: GitHubClient = GitHubClient(),
        store: StoreClient = StoreClient(),
    ):
        self.git = git
        self.gh = gh
        self.store = store

    def create_draft(
        self,
        title: Optional[str],
        body: Optional[str]
    ) -> int:
        """Create draft PR with flow metadata."""
        # 1. Get current context
        branch = self.git.get_current_branch()
        state = self.store.get_flow_state(branch)

        # 2. Build PR body
        if not body:
            body = self._build_pr_body(state, branch)

        # 3. Create PR
        pr_number = self.gh.create_pr(
            title=title or f"Draft PR for {branch}",
            body=body,
            draft=True
        )

        # 4. Update state
        self.store.update_pr_number(branch, pr_number)

        return pr_number
```

---

## Migration Path

### Phase 1: Add Dependencies (不破坏现有代码)

```bash
# 添加依赖
pip install typer rich pydantic loguru pyyaml

# 更新 requirements.txt 或 pyproject.toml
```

### Phase 2: Add Type Hints (渐进式)

```python
# 1. 先添加类型注解
# 2. 运行 mypy 检查
# 3. 修复类型错误
```

### Phase 3: Refactor Manager (逐步拆分)

```python
# 1. 提取 GitClient
# 2. 提取 GitHubClient
# 3. 提取 PRService
# 4. Manager 变成薄调度层
```

### Phase 4: Migrate to Typer (保持兼容)

```python
# 1. 创建新的 Typer CLI
# 2. 保留 argparse 作为 fallback
# 3. 逐步迁移命令
```

---

## Summary

### Critical Issues (Must Fix)
- ❌ Manager 类过于臃肿 (563 行)
- ❌ 缺少类型注解 (10% coverage)

### High Priority (Should Fix)
- ⚠️ 未使用现代 Python 工具链
- ⚠️ 缺少 -v 参数
- ⚠️ 直接调用 subprocess

### Medium Priority (Consider)
- ℹ️ 缺少结构化日志
- ℹ️ 缺少配置管理

### Recommendation

**短期** (Phase 3 验收):
- ✅ 功能已完整实现
- ✅ 测试通过
- ⚠️ 可以验收，但需要记录技术债

**中期** (Phase 4-5):
1. 添加 typer, rich, pydantic, loguru 依赖
2. 重构 Manager 为薄调度层
3. 添加完整类型注解
4. 实现 -v 参数

**长期** (v3.1+):
1. 完整迁移到 Typer CLI
2. 完善测试覆盖
3. 添加配置管理

---

**Reviewer**: Claude Sonnet 4.6
**Date**: 2026-03-15
**Status**: ⚠️ WARNING - Needs Refactoring