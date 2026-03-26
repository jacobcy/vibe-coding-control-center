# Flow 依赖管理 P0 级问题修复计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**目标**: 修复两个关键的 P0 级问题，确保 Flow 状态模型一致性和正确的状态检查逻辑。

**技术栈**: Python 3.10+, Typer, pytest

---

## Phase 1: 模型定义修复

### Task 1.1: 修复 Flow 模型状态定义

**文件**: `src/vibe3/models/flow.py`

**Step 1: 定位并修复模型定义**

找到 `flow_status` 字段定义（第 39 行左右），添加 `aborted`：

```python
# 修改前
flow_status: Literal["active", "blocked", "done", "stale"] = "active"

# 修改后
flow_status: Literal["active", "blocked", "done", "stale", "aborted"] = "active"
```

**Step 2: 验证修复**

运行类型检查：
```bash
uv run mypy src/vibe3/models/flow.py
```

Expected: PASS

---

## Phase 2: Flow new 状态检查修复

### Task 2.1: 添加命令参数

**文件**: `src/vibe3/commands/flow.py`

**Step 1: 添加参数到 new() 函数**

在 `new()` 函数参数列表中添加：

```python
def new(
    name: Annotated[str, typer.Argument(help="Flow name")],
    task: Annotated[str | None, typer.Option(help="Task ID to bind")] = None,
    spec: Annotated[str | None, typer.Option("--spec", help="Spec file path")] = None,
    create_branch: Annotated[
        bool,
        typer.Option(
            "--create-branch",
            "-c",
            help="Create new branch (task/<name>) instead of binding current branch",
        ),
    ] = False,
    start_ref: Annotated[
        str,
        typer.Option(
            "--start-ref", help="Start ref for new branch (default: origin/main)"
        ),
    ] = "origin/main",
    actor: Annotated[str, typer.Option(help="Actor creating the flow")] = "system",
    force: Annotated[  # 新增参数
        bool,
        typer.Option("--yes", "-y", help="Force create on branch with existing flow"),
    ] = False,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
) -> None:
```

### Task 2.2: 实现状态检查逻辑

**文件**: `src/vibe3/commands/flow.py`

**Step 1: 修改非创建分支模式的逻辑**

找到第 128-140 行的代码，替换为：

```python
else:
    branch = git.get_current_branch()
    existing_flow = service.get_flow_status(branch)

    if existing_flow:
        status = existing_flow.flow_status

        # Active/blocked flow: 阻止创建
        if status in ["active", "blocked"]:
            if not force:
                console.print(
                    f"[red]Error: Branch '{branch}' has active flow: {existing_flow.flow_slug}[/]"
                )
                console.print(
                    "[yellow]Use --yes to force create, or switch to another branch first[/]"
                )
                raise typer.Exit(1)

        # Done/aborted/stale flow: 允许创建，给出提示
        if status in ["done", "aborted", "stale"] and not force:
            console.print(
                f"[yellow]Warning: Branch '{branch}' has completed flow: {existing_flow.flow_slug}[/]"
            )
            console.print(
                f"[yellow]Creating new flow with base: {start_ref}[/]"
            )

    flow = service.create_flow(slug=name, branch=branch)
```

**Step 2: 更新 docstring**

```python
"""Create a new flow.

Use -c to create new branch (task/<name>), otherwise binds to current branch.

If current branch already has a flow:
- Active/blocked flow: Error (use --yes to force)
- Done/aborted/stale flow: Warning, then proceed

Examples:
    vibe3 flow new my-feature
    vibe3 flow new my-feature -c
    vibe3 flow new my-feature --yes  # Force create on branch with active flow
"""
```

---

## Phase 3: 测试验证

### Task 3.1: 创建测试文件

**文件**: `tests/vibe3/commands/test_flow_new_status_check.py`

**Step 1: 写测试**

```python
"""Tests for flow new status checking logic."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.models.flow import FlowStatusResponse

runner = CliRunner()


class TestFlowNewStatusCheck:
    """Tests for flow new status checking."""

    @patch("vibe3.commands.flow.FlowService")
    @patch("vibe3.commands.flow.GitClient")
    def test_active_flow_blocks_creation(
        self, mock_git_class, mock_service_class
    ):
        """Active flow should block creation."""
        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "feature/test"
        mock_git_class.return_value = mock_git

        mock_service = MagicMock()
        mock_flow = MagicMock(spec=FlowStatusResponse)
        mock_flow.flow_status = "active"
        mock_flow.flow_slug = "test-flow"
        mock_service.get_flow_status.return_value = mock_flow
        mock_service_class.return_value = mock_service

        result = runner.invoke(app, ["flow", "new", "new-flow"])

        assert result.exit_code == 1
        assert "already has active flow" in result.output.lower()
        mock_service.create_flow.assert_not_called()

    @patch("vibe3.commands.flow.FlowService")
    @patch("vibe3.commands.flow.GitClient")
    def test_active_flow_force_create(
        self, mock_git_class, mock_service_class
    ):
        """Active flow with --yes should force create."""
        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "feature/test"
        mock_git_class.return_value = mock_git

        mock_service = MagicMock()
        mock_flow = MagicMock(spec=FlowStatusResponse)
        mock_flow.flow_status = "active"
        mock_flow.flow_slug = "test-flow"
        mock_service.get_flow_status.return_value = mock_flow
        mock_service.create_flow.return_value = MagicMock(
            flow_slug="new-flow", branch="feature/test"
        )
        mock_service_class.return_value = mock_service

        result = runner.invoke(app, ["flow", "new", "new-flow", "--yes"])

        assert result.exit_code == 0
        mock_service.create_flow.assert_called_once()

    @patch("vibe3.commands.flow.FlowService")
    @patch("vibe3.commands.flow.GitClient")
    def test_done_flow_allows_creation(
        self, mock_git_class, mock_service_class
    ):
        """Done flow should allow creation with warning."""
        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "feature/test"
        mock_git_class.return_value = mock_git

        mock_service = MagicMock()
        mock_flow = MagicMock(spec=FlowStatusResponse)
        mock_flow.flow_status = "done"
        mock_flow.flow_slug = "test-flow"
        mock_service.get_flow_status.return_value = mock_flow
        mock_service.create_flow.return_value = MagicMock(
            flow_slug="new-flow", branch="feature/test"
        )
        mock_service_class.return_value = mock_service

        result = runner.invoke(app, ["flow", "new", "new-flow"])

        assert result.exit_code == 0
        assert "warning" in result.output.lower()
        mock_service.create_flow.assert_called_once()

    @patch("vibe3.commands.flow.FlowService")
    @patch("vibe3.commands.flow.GitClient")
    def test_aborted_flow_allows_creation(
        self, mock_git_class, mock_service_class
    ):
        """Aborted flow should allow creation with warning."""
        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "feature/test"
        mock_git_class.return_value = mock_git

        mock_service = MagicMock()
        mock_flow = MagicMock(spec=FlowStatusResponse)
        mock_flow.flow_status = "aborted"
        mock_flow.flow_slug = "test-flow"
        mock_service.get_flow_status.return_value = mock_flow
        mock_service.create_flow.return_value = MagicMock(
            flow_slug="new-flow", branch="feature/test"
        )
        mock_service_class.return_value = mock_service

        result = runner.invoke(app, ["flow", "new", "new-flow"])

        assert result.exit_code == 0
        assert "warning" in result.output.lower()
        mock_service.create_flow.assert_called_once()
```

**Step 2: 运行测试**

```bash
uv run pytest tests/vibe3/commands/test_flow_new_status_check.py -xvs
```

Expected: PASS (所有测试)

---

## Phase 4: 最终验证

### Task 4.1: 运行完整测试套件

```bash
uv run pytest tests/vibe3/ -q
```

Expected: 全绿

### Task 4.2: 运行代码质量检查

```bash
uv run ruff check src/vibe3/
uv run mypy src/vibe3/
```

Expected: PASS

---

## Deliverables

- [ ] 模型定义包含 `aborted` 状态
- [ ] `flow new` 正确检查 flow 状态
- [ ] Active/blocked flow 阻止重复创建（除非 --yes）
- [ ] Done/aborted/stale flow 允许创建并提示
- [ ] 测试覆盖所有场景
- [ ] 所有测试通过
- [ ] 类型检查通过
- [ ] 代码格式检查通过

---

## Risks & Mitigations

**风险1**: 破坏现有功能
- 缓解: 完整测试套件验证

**风险2**: 用户不理解新的行为
- 缓解: 清晰的错误提示和警告信息

**风险3**: 强制创建导致数据丢失
- 缓解: 明确的 --yes 标志要求用户确认

---

## Success Criteria

1. ✅ 模型定义包含 `aborted`
2. ✅ `flow new` 能正确区分 flow 状态
3. ✅ Active/blocked flow 不允许重复创建（除非 --yes）
4. ✅ Done/aborted/stale flow 允许创建新 flow
5. ✅ 所有测试通过
6. ✅ 类型检查通过
7. ✅ 代码格式检查通过