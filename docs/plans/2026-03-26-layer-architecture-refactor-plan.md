# 分层架构重构计划 - 消除 Command 层违规与代码重复

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**目标**：修复分层架构违规，消除代码重复，建立清晰的分层边界。

**背景**：代码审查发现 Command 层直接访问 Client 层，违反分层原则。同时存在重复代码和职责不清的问题。

**技术栈**：Python 3.10+, Typer, pytest

---

## 架构原则

### 正确的分层结构

```
Presentation Layer (CLI)
    ↓ 调用
Application Layer (Service)
    ↓ 调用
Domain Layer (Models)
    ↓ 调用
Infrastructure Layer (Clients)
```

**规则**：
- Command 层只调用 Service 层，不直接访问 Client
- Service 层协调 Client 和 Model
- Client 层只负责外部系统交互（Git, SQLite, GitHub API）

---

## Phase 1: 提取公共基础设施

### Task 1.1: 创建 Command 层公共工具模块

**文件**：`src/vibe3/commands/common.py`

**Step 1: 创建文件并提取 `_trace_scope`**

```python
"""Common utilities for command layer."""

from contextlib import nullcontext
from typing import Any

from vibe3.observability.logger import setup_logging
from vibe3.observability.trace import trace_context


def trace_scope(
    trace: bool, command: str, domain: str = "flow", **kwargs: Any
) -> Any:  # type: ignore[no-untyped-def]
    """Create trace context for command execution.

    Args:
        trace: Enable trace mode
        command: Command name
        domain: Domain name (default: flow)
        **kwargs: Additional context fields

    Returns:
        Trace context manager or nullcontext

    Example:
        >>> with trace_scope(True, "flow show", flow_name="my-feature"):
        ...     # Command logic here
    """
    if trace:
        setup_logging(verbose=2)
        return trace_context(command=command, domain=domain, **kwargs)
    return nullcontext()
```

**Step 2: 更新 flow.py 使用公共函数**

在 `src/vibe3/commands/flow.py` 中：

```python
# 删除本地 _trace_scope 函数
# 在文件顶部添加导入
from vibe3.commands.common import trace_scope

# 所有 _trace_scope 调用改为 trace_scope
with _trace_scope(trace, "flow add", name=name):
# 改为
with trace_scope(trace, "flow add", name=name):
```

**Step 3: 更新 handoff_write.py**

同样的处理：删除本地 `_trace_scope`，导入公共函数。

**验证**：

```bash
# 类型检查
uv run mypy src/vibe3/commands/common.py
uv run mypy src/vibe3/commands/flow.py
uv run mypy src/vibe3/commands/handoff_write.py

# 功能测试
uv run python src/vibe3/cli.py flow show --trace
uv run python src/vibe3/cli.py handoff write --help
```

---

## Phase 2: FlowService 增强 Git 能力

### Task 2.1: FlowService 添加 GitClient 依赖

**文件**：`src/vibe3/services/flow_service.py`

**Step 1: 修改 __init__ 方法**

```python
from vibe3.clients.git_client import GitClient

class FlowService(FlowAutoEnsureMixin, FlowLifecycleMixin):
    """Service for managing flow state."""

    def __init__(
        self,
        store: SQLiteClient | None = None,
        git_client: GitClient | None = None,
        config: VibeConfig | None = None,
    ) -> None:
        """Initialize flow service.

        Args:
            store: SQLiteClient instance for persistence
            git_client: GitClient instance for git operations
            config: VibeConfig instance for configuration
        """
        self.store = store or SQLiteClient()
        self.git_client = git_client or GitClient()
        self.config = config or VibeConfig.get_defaults()
```

**Step 2: 添加便捷方法**

```python
def get_current_branch(self) -> str:
    """Get current git branch.

    Returns:
        Current branch name

    Example:
        >>> service = FlowService()
        >>> branch = service.get_current_branch()
    """
    return self.git_client.get_current_branch()
```

**验证**：

```bash
uv run mypy src/vibe3/services/flow_service.py
```

---

## Phase 3: 消除 Command 层直接访问 Client

### Task 3.1: 重构 flow.py 的 show 命令

**文件**：`src/vibe3/commands/flow.py`

**修改前**：

```python
@app.command()
def show(...):
    git = GitClient()  # ❌ 直接访问 Client
    service = FlowService()
    branch = flow_name if flow_name else git.get_current_branch()
```

**修改后**：

```python
@app.command()
def show(...):
    service = FlowService()  # ✓ 只使用 Service
    branch = flow_name if flow_name else service.get_current_branch()
    timeline = service.get_flow_timeline(branch)
```

**影响范围**：
- `flow.py` 中约 8 处 `GitClient()` 调用
- 需要逐个函数重构

**验证**：

```bash
uv run python src/vibe3/cli.py flow show
uv run python src/vibe3/cli.py flow list
```

---

### Task 3.2: 重构 handoff_read.py

**文件**：`src/vibe3/commands/handoff_read.py`

**修改前**：

```python
def list_handoffs(...):
    git = GitClient()      # ❌
    store = SQLiteClient() # ❌
    target_branch = branch if branch else git.get_current_branch()
    events_data = store.get_events(target_branch, event_type_prefix="handoff_")
```

**修改后**：

```python
def list_handoffs(...):
    service = FlowService()  # ✓
    target_branch = branch if branch else service.get_current_branch()
    # 需要在 FlowService 中添加 get_handoff_events 方法
    events_data = service.get_handoff_events(target_branch, limit=None)
```

**需要在 FlowService 中添加方法**：

```python
def get_handoff_events(
    self, branch: str, event_type_prefix: str = "handoff_", limit: int | None = None
) -> list[FlowEvent]:
    """Get handoff events for branch.

    Args:
        branch: Branch name
        event_type_prefix: Event type filter prefix
        limit: Maximum number of events

    Returns:
        List of FlowEvent objects
    """
    events_data = self.store.get_events(
        branch, event_type_prefix=event_type_prefix, limit=limit
    )
    return [FlowEvent(**e) for e in events_data]
```

**验证**：

```bash
uv run python src/vibe3/cli.py handoff list
uv run python src/vibe3/cli.py handoff show
```

---

### Task 3.3: 重构其他命令文件

**文件列表**：
- `src/vibe3/commands/flow_lifecycle.py` (3 处)
- `src/vibe3/commands/flow_status.py` (1 处)
- `src/vibe3/commands/task_bridge.py` (2 处)
- `src/vibe3/commands/task.py` (多处)

**验证**：

```bash
# 全局搜索确认无遗漏
grep -r "GitClient()" src/vibe3/commands/
grep -r "SQLiteClient()" src/vibe3/commands/
```

---

## Phase 4: 合并 Handoff Service 职责

### Task 4.1: 分析当前 Handoff 相关文件

**当前文件**：

1. `handoff_service.py` - 主 Service（面向对象）
2. `handoff_event_service.py` - 事件辅助函数（函数式）
3. `handoff_recorder_unified.py` - 统一记录函数（函数式）
4. `handoff_recorder.py` - 旧记录函数（被 HandoffService 调用）

**问题**：
- 函数式和面向对象混用
- 职责重叠
- 调用链不清晰

---

### Task 4.2: 设计新的 HandoffService 结构

**目标结构**：

```python
class HandoffService:
    """Unified service for handoff management."""

    # 文件管理
    def ensure_handoff_dir(self) -> Path
    def ensure_current_handoff(self, force: bool = False) -> Path
    def read_current_handoff(self) -> str
    def append_current_handoff(self, message: str, actor: str, kind: str) -> Path

    # Artifact 创建（从 handoff_event_service.py 合并）
    def create_artifact(self, prefix: str, content: str | None) -> tuple[str, Path] | None

    # 事件持久化（从 handoff_event_service.py 合并）
    def persist_event(
        self,
        branch: str,
        event_type: str,
        actor: str,
        detail: str,
        refs: dict[str, str],
        flow_state_updates: dict[str, object] | None = None,
    ) -> None

    # 统一记录（从 handoff_recorder_unified.py 合并）
    def record_unified(self, record: HandoffRecord) -> Path | None

    # 向后兼容方法（调用 record_unified）
    def record_plan(self, ...) -> None
    def record_report(self, ...) -> None
    def record_audit(self, ...) -> None
```

---

### Task 4.3: 实施合并（可选，Phase 4 可以独立 PR）

**步骤**：

1. 将 `handoff_event_service.py` 中的函数改为 HandoffService 的方法
2. 将 `handoff_recorder_unified.py` 中的函数改为 HandoffService 的方法
3. 更新所有调用点
4. 删除废弃文件

**验证**：

```bash
# 测试 handoff 功能
uv run pytest tests/vibe3/services/test_handoff_*.py -v
```

---

## 验证计划

### 单元测试

每个 Phase 完成后运行：

```bash
# 类型检查
uv run mypy src/vibe3/

# 现有测试
uv run pytest tests/vibe3/

# 架构验证（新增）
# 检查 Command 层是否还有直接访问 Client 的代码
grep -r "GitClient()" src/vibe3/commands/ && echo "FAIL: Command 层违规" || echo "PASS"
grep -r "SQLiteClient()" src/vibe3/commands/ && echo "FAIL: Command 层违规" || echo "PASS"
```

### 集成测试

```bash
# Flow 命令完整流程
uv run python src/vibe3/cli.py flow create test-feature --base main
uv run python src/vibe3/cli.py flow show
uv run python src/vibe3/cli.py flow list
uv run python src/vibe3/cli.py flow done

# Handoff 命令完整流程
uv run python src/vibe3/cli.py handoff list
uv run python src/vibe3/cli.py handoff show
```

---

## 实施顺序

**建议按以下顺序独立 PR**：

1. **PR 1: Phase 1** - 提取公共基础设施（低风险）
2. **PR 2: Phase 2** - FlowService 增强（低风险）
3. **PR 3: Phase 3** - 消除分层违规（高风险，需仔细测试）
4. **PR 4: Phase 4** - 合并 Handoff Service（可选，中等风险）

每个 PR 应该：
- 包含完整的测试
- 更新相关文档
- 在 PR 描述中引用此计划

---

## 风险评估

### 高风险区域

1. **FlowService 构造函数签名变更**
   - 影响：所有创建 FlowService 实例的代码
   - 缓解：保持向后兼容，使用可选参数

2. **Command 层重构**
   - 影响：所有 flow/handoff/task 命令
   - 缓解：逐个命令重构，每次验证

### 测试覆盖

- 确保现有测试不回归
- 为新增方法添加单元测试
- 添加架构验证测试

---

## 预期收益

1. **架构清晰**：严格的分层边界
2. **可测试性**：Command 层只需 mock Service
3. **可维护性**：消除重复代码
4. **一致性**：统一的设计模式