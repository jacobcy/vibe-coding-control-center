# Issue #331: Commands 层重构计划

## 问题概述

commands/ 层文件体积远超合理范围，混合了参数解析、业务决策、服务组装、格式化输出等多种职责，违反"薄命令层"原则。

## 目标

1. commands/ 文件目标：< 100 行，仅含参数定义、参数校验、调用 usecase、调用 UI 渲染
2. 将 `_build_flow_usecase()` 等工厂函数迁移到对应的 usecase 类方法
3. 将 `_merge_issue_refs()` 等参数合并逻辑迁移到 usecase 的输入校验层
4. `check.py` 的四路分支逻辑下沉到 `CheckService` 的统一方法

## 重构范围

### 1. `commands/flow.py` (291 行 → 目标 < 100 行)

**问题函数：**
- `_build_flow_usecase()` (行 67-72) - 服务组装工厂
- `_merge_issue_refs()` (行 81-95) - 参数合并业务逻辑
- `_resolve_flow_name()` (行 98-108) - 名称解析逻辑

**重构步骤：**

#### 1.1 迁移 `_build_flow_usecase()` 到 `FlowUsecase.create()`

**当前代码：**
```python
def _build_flow_usecase(flow_service: FlowService | None = None) -> FlowUsecase:
    return FlowUsecase(
        flow_service=flow_service or FlowService(),
        task_service=TaskService(),
        handoff_service=HandoffService(),
    )
```

**目标：** 在 `FlowUsecase` 类中添加 `create()` 类方法

**修改文件：** `src/vibe3/services/flow_usecase.py`

```python
@classmethod
def create(cls, flow_service: FlowService | None = None) -> FlowUsecase:
    """Create FlowUsecase with default dependencies."""
    return cls(
        flow_service=flow_service or FlowService(),
        task_service=TaskService(),
        handoff_service=HandoffService(),
    )
```

#### 1.2 迁移 `_merge_issue_refs()` 到 usecase 输入校验层

**当前代码：**
```python
def _merge_issue_refs(
    primary: str | None,
    tail: List[str] | None,
    *,
    primary_hint: str,
) -> str | List[str] | None:
    """Support both repeated option and trailing-args styles for issue refs."""
    tail = tail or []
    if not tail:
        return primary
    if primary is None:
        raise typer.BadParameter(
            f"Additional issue refs require '{primary_hint}' prefix."
        )
    return [primary, *tail]
```

**目标：** 迁移到 `FlowUsecase` 的输入校验方法

**修改文件：** `src/vibe3/services/flow_usecase.py`

```python
@staticmethod
def validate_issue_refs(
    primary: str | None,
    tail: List[str] | None,
    *,
    primary_hint: str,
) -> str | List[str] | None:
    """Validate and merge issue references."""
    tail = tail or []
    if not tail:
        return primary
    if primary is None:
        raise ValueError(f"Additional issue refs require '{primary_hint}' prefix.")
    return [primary, *tail]
```

#### 1.3 迁移 `_resolve_flow_name()` 到 `FlowService`

**当前代码：**
```python
def _resolve_flow_name(
    name: str | None, flow_service: FlowService | None = None
) -> str:
    """Return explicit *name* or derive slug from the current branch."""
    if name:
        return name
    flow_service = flow_service or FlowService()
    branch = flow_service.get_current_branch()
    if branch == "HEAD":
        raise typer.BadParameter("Cannot infer flow name from detached HEAD")
    return branch.rsplit("/", 1)[-1] or branch
```

**目标：** 迁移到 `FlowService` 的方法

**修改文件：** `src/vibe3/services/flow_service.py`

```python
def resolve_flow_name(self, name: str | None = None) -> str:
    """Return explicit name or derive slug from current branch."""
    if name:
        return name
    branch = self.get_current_branch()
    if branch == "HEAD":
        raise ValueError("Cannot infer flow name from detached HEAD")
    return branch.rsplit("/", 1)[-1] or branch
```

### 2. `commands/check.py` (139 行 → 目标 < 100 行)

**问题：** 四路分支逻辑（init/all/single/fix）直接在命令处理器中

**重构步骤：**

#### 2.1 将分支逻辑下沉到 `CheckService`

**修改文件：** `src/vibe3/services/check_service.py`

添加统一方法：
```python
def execute_check(
    self,
    mode: Literal["default", "init", "all", "fix"],
    branch: str | None = None
) -> CheckResult:
    """Unified check execution with mode-based routing."""
    if mode == "init":
        return self._handle_init_mode()
    elif mode == "all":
        return self._handle_all_mode()
    elif mode == "fix":
        return self._handle_fix_mode(branch)
    else:
        return self._handle_default_mode(branch)

def _handle_init_mode(self) -> CheckResult:
    """Handle --init mode: scan merged PRs to back-fill task_issue_number."""
    result = self.init_remote_index()
    return CheckResult(
        mode="init",
        success=True,
        summary=f"Done  total={result.total_flows}  updated={result.updated}  skipped={result.skipped}",
        details={"unresolvable": result.unresolvable} if result.unresolvable else {}
    )

def _handle_all_mode(self) -> CheckResult:
    """Handle --all mode: check every flow."""
    results = self.verify_all_flows()
    invalid = [r for r in results if not r.is_valid]
    return CheckResult(
        mode="all",
        success=len(invalid) == 0,
        summary=f"All {len(results)} flows passed" if not invalid else f"{len(invalid)}/{len(results)} flows have issues",
        details={"invalid": invalid}
    )

def _handle_fix_mode(self, branch: str | None) -> CheckResult:
    """Handle --fix mode: auto-fix current branch."""
    result_single = self.verify_current_flow()
    if result_single.is_valid:
        return CheckResult(mode="fix", success=True, summary="All checks passed")

    fix_result = self.auto_fix(result_single.issues)
    return CheckResult(
        mode="fix",
        success=fix_result.success,
        summary="All issues fixed" if fix_result.success else f"Error: {fix_result.error}",
        details={"issues": result_single.issues}
    )

def _handle_default_mode(self, branch: str | None) -> CheckResult:
    """Handle default mode: check current branch."""
    result_single = self.verify_current_flow()
    return CheckResult(
        mode="default",
        success=result_single.is_valid,
        summary="All checks passed" if result_single.is_valid else f"Issues found for branch '{result_single.branch}'",
        details={"issues": result_single.issues}
    )
```

#### 2.2 简化 `commands/check.py`

**重构后代码：**
```python
@app.callback(invoke_without_command=True)
def check(
    ctx: typer.Context,
    fix: Annotated[bool, typer.Option("--fix")] = False,
    all_flows: Annotated[bool, typer.Option("--all")] = False,
    init: Annotated[bool, typer.Option("--init")] = False,
    trace: Annotated[bool, typer.Option("--trace")] = False,
) -> None:
    """Verify handoff store consistency."""
    if trace:
        setup_logging(verbose=2)

    trace_ctx = trace_context(command="check", domain="check") if trace else None
    if trace_ctx:
        trace_ctx.__enter__()

    try:
        service = CheckService()
        mode = "init" if init else "all" if all_flows else "fix" if fix else "default"
        result = service.execute_check(mode)

        if result.success:
            typer.echo(f"✓ {result.summary}")
        else:
            typer.echo(f"✗ {result.summary}", err=True)
            if not fix and mode == "default":
                typer.echo("\n  → Run [cyan]vibe3 check --fix[/] to auto-fix", err=True)
            raise typer.Exit(code=1)
    finally:
        if trace_ctx:
            trace_ctx.__exit__(None, None, None)
```

### 3. 其他文件检查

需要检查的文件：
- `commands/handoff_read.py` (272 行)
- `commands/run.py` (230 行)
- `commands/review.py` (192 行)

## 实施顺序

1. **Phase 1: FlowUsecase 重构**
   - [ ] 在 `FlowUsecase` 中添加 `create()` 类方法
   - [ ] 在 `FlowUsecase` 中添加 `validate_issue_refs()` 静态方法
   - [ ] 在 `FlowService` 中添加 `resolve_flow_name()` 方法
   - [ ] 更新 `commands/flow.py` 使用新方法
   - [ ] 运行测试验证

2. **Phase 2: CheckService 重构**
   - [ ] 在 `CheckService` 中添加 `execute_check()` 统一方法
   - [ ] 添加对应的私有方法处理各模式
   - [ ] 简化 `commands/check.py`
   - [ ] 运行测试验证

3. **Phase 3: 其他文件重构**（如果需要）
   - [ ] 检查 `handoff_read.py`
   - [ ] 检查 `run.py`
   - [ ] 检查 `review.py`

## 测试策略

1. **单元测试**：确保重构后的代码行为不变
2. **集成测试**：验证命令行接口功能正常
3. **回归测试**：确保现有功能不受影响

## 验证步骤

1. 运行现有测试：`uv run pytest tests/vibe3 -v`
2. 运行 linting：`uv run ruff check src`
3. 运行类型检查：`uv run mypy src`
4. 手动测试命令行功能

## 风险与缓解

1. **风险**：重构可能破坏现有功能
   - **缓解**：逐步重构，每步都运行测试

2. **风险**：依赖关系复杂
   - **缓解**：先重构独立的方法，再处理依赖

3. **风险**：测试覆盖不足
   - **缓解**：补充测试用例

## 成功标准

1. [ ] `commands/flow.py` < 100 行
2. [ ] `commands/check.py` < 100 行
3. [ ] 所有现有测试通过
4. [ ] 命令行功能正常
5. [ ] 代码符合"薄命令层"原则