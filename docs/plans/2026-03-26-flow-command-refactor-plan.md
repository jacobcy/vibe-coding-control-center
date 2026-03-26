# Flow 命令重构实施计划 - 拆分 new 为 add 和 create

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**目标**：重构 flow 命令体系，拆分 `flow new` 为 `flow add`（注册）和 `flow create`（创建），并实现正确的依赖反查逻辑。

**背景**：根据 `.agent/reports/flow-redesign-proposal.md` 的分析，当前 `flow new` 命令语义混淆，需要拆分成两个语义清晰的命令。

**技术栈**：Python 3.10+, Typer, pytest

---

## Phase 1: 数据层 - 添加依赖反查方法

### Task 1.1: 添加 get_flow_dependents() 方法

**文件**：`src/vibe3/clients/sqlite_client.py`

**Step 1: 在 SQLiteClient 类中添加方法**

在类的方法区域添加：

```python
def get_flow_dependents(self, branch: str) -> list[str]:
    """Get branches that depend on the given branch.

    Args:
        branch: Branch name to check dependents for

    Returns:
        List of branch names that depend on this branch

    Example:
        >>> store = SQLiteClient()
        >>> dependents = store.get_flow_dependents("feature/A")
        >>> # ["feature/B"] or ["feature/B", "feature/C"]
    """
    with self._get_connection() as conn:
        cursor = conn.execute(
            """
            SELECT DISTINCT fs.branch
            FROM flow_state fs
            JOIN flow_issue_links fil ON fs.task_issue_number = fil.issue_number
            WHERE fil.linked_issue_number = (
                SELECT task_issue_number
                FROM flow_state
                WHERE branch = ?
            )
            AND fil.role = 'dependency'
            AND fs.flow_status = 'active'
            ORDER BY fs.branch
            """,
            (branch,),
        )
        return [row[0] for row in cursor.fetchall()]
```

**Step 2: 验证类型检查**

```bash
uv run mypy src/vibe3/clients/sqlite_client.py
```

Expected: PASS

---

## Phase 2: 服务层 - 实现依赖反查逻辑

### Task 2.1: 修改 close_flow() 实现依赖反查

**文件**：`src/vibe3/services/flow_lifecycle.py`

**Step 1: 找到 close_flow 方法**

定位 `FlowLifecycleMixin.close_flow()` 方法（大约在第 120-150 行）。

**Step 2: 在方法末尾添加依赖反查逻辑**

在删除分支、标记状态后，添加：

```python
# 导入放在文件顶部
from vibe3.clients.sqlite_client import SQLiteClient

def close_flow(self: Any, branch: str, check_pr: bool = True) -> None:
    # ... 现有逻辑：检查 PR、删除分支、标记状态 ...

    # === 新增：依赖反查逻辑 ===
    try:
        store = SQLiteClient()
        dependents = store.get_flow_dependents(branch)

        if len(dependents) == 1:
            # 单依赖：自动切换
            dependent_branch = dependents[0]
            self.git.switch_branch(dependent_branch)
            logger.bind(
                domain="flow",
                action="close",
                branch=branch,
                dependent=dependent_branch,
            ).info("Switched to dependent branch")

        elif len(dependents) > 1:
            # 多依赖：只提示，不交互
            logger.warning(
                f"Multiple flows depend on '{branch}': {', '.join(dependents)}\n"
                f"Use 'vibe3 flow switch <branch>' to switch to the desired branch"
            )
            # 默认切换到 main
            self.git.switch_branch("main")
            try:
                self.git._run(["pull"])
                logger.info("Switched to main and pulled latest changes")
            except Exception as e:
                logger.warning(f"Failed to pull: {e}")

        else:
            # 无依赖：切换到 main
            self.git.switch_branch("main")
            try:
                self.git._run(["pull"])
                logger.info("Switched to main and pulled latest changes")
            except Exception as e:
                logger.warning(f"Failed to pull: {e}")

    except Exception as e:
        # 依赖反查失败不影响主流程
        logger.warning(f"Failed to check dependents: {e}")
        # 仍然切换到 main
        self.git.switch_branch("main")
        try:
            self.git._run(["pull"])
        except Exception:
            pass
```

**Step 3: 运行类型检查**

```bash
uv run mypy src/vibe3/services/flow_lifecycle.py
```

Expected: PASS

---

## Phase 3: 命令层 - 拆分 flow new

### Task 3.1: 创建 flow add 命令

**文件**：`src/vibe3/commands/flow.py`

**Step 1: 重命名 new() 函数为 add()**

找到 `new()` 函数（第 77-167 行），重命名为 `add()`：

```python
@app.command(name="add")
def add(
    name: Annotated[str, typer.Argument(help="Flow name")],
    task: Annotated[str | None, typer.Option(help="Task ID to bind")] = None,
    spec: Annotated[str | None, typer.Option("--spec", help="Spec file path")] = None,
    force: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Force add on branch with existing flow"),
    ] = False,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
) -> None:
    """Add flow to current branch.

    This command registers a flow on the current branch.
    Use 'flow create' to create a new branch with flow.

    If current branch already has a flow:
    - Active/blocked flow: Error (use --yes to force)
    - Done/aborted/stale flow: Warning, then proceed

    Examples:
        vibe3 flow add my-feature
        vibe3 flow add my-feature --yes  # Force add on branch with active flow
    """
    with _trace_scope(trace, "flow add", name=name):
        logger.bind(command="flow add", name=name, task=task).info("Adding flow")

        git = GitClient()
        service = FlowService()
        branch = git.get_current_branch()

        # 检查是否已有 flow
        existing_flow = service.get_flow_status(branch)
        if existing_flow:
            status = existing_flow.flow_status

            # Active/blocked flow: 阻止注册
            if status in ["active", "blocked"]:
                if not force:
                    console.print(
                        f"[red]Error: Branch '{branch}' has active flow: "
                        f"{existing_flow.flow_slug}[/]"
                    )
                    console.print(
                        "[yellow]Use --yes to force add, or switch to another branch first[/]"
                    )
                    raise typer.Exit(1)

            # Done/aborted/stale flow: 允许注册，给出提示
            if status in ["done", "aborted", "stale"] and not force:
                console.print(
                    f"[yellow]Warning: Branch '{branch}' has completed flow: "
                    f"{existing_flow.flow_slug}[/]"
                )
                console.print("[yellow]Adding new flow to this branch[/]")

        # 注册 flow
        flow = service.create_flow(slug=name, branch=branch)

        # 绑定 task
        if task:
            try:
                _bind_task_to_flow(branch, task, "system", command="flow add")
            except ValueError:
                logger.bind(command="flow add", task=task).warning(
                    "Invalid task ID format, skipping binding"
                )

        # 绑定 spec_ref
        if spec:
            store = SQLiteClient()
            store.update_flow_state(branch, spec_ref=spec, latest_actor="system")
            store.add_event(branch, "spec_bound", "system", detail=f"Spec bound: {spec}")
            logger.bind(command="flow add", spec=spec).info("Spec bound to flow")

        # 自动初始化 handoff current.md
        HandoffService().ensure_current_handoff()

        if json_output:
            typer.echo(json.dumps(flow.model_dump(), indent=2, default=str))
        else:
            render_flow_created(flow, task)
```

**Step 2: 移除 create_branch 相关逻辑**

确保移除：
- `create_branch` 参数
- `start_ref` 参数
- `actor` 参数
- 创建分支的逻辑

### Task 3.2: 创建 flow create 命令

**文件**：`src/vibe3/commands/flow.py`

**Step 1: 创建新的 create() 函数**

在 `add()` 函数之后添加：

```python
@app.command(name="create")
def create(
    name: Annotated[str, typer.Argument(help="Flow name")],
    task: Annotated[str | None, typer.Option(help="Task ID to bind")] = None,
    spec: Annotated[str | None, typer.Option("--spec", help="Spec file path")] = None,
    base: Annotated[
        str,
        typer.Option(
            "--base",
            "-b",
            help="Base branch (default: main, also supports 'current' or branch name)",
        ),
    ] = "main",
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
) -> None:
    """Create new branch with flow.

    This command creates a new branch and registers a flow on it.

    Base branch options:
    - main (default): Create from origin/main
    - current: Create from current branch
    - <branch-name>: Create from specified branch

    Examples:
        vibe3 flow create my-feature
        vibe3 flow create my-feature --base main
        vibe3 flow create my-feature --base current
        vibe3 flow create my-feature --base feature/A
    """
    with _trace_scope(trace, "flow create", name=name, base=base):
        logger.bind(command="flow create", name=name, base=base, task=task).info(
            "Creating flow with new branch"
        )

        git = GitClient()
        service = FlowService()

        # 确定基础分支
        if base == "main":
            start_ref = "origin/main"
        elif base == "current":
            start_ref = git.get_current_branch()
        else:
            # 用户指定的分支名
            start_ref = base

        # 检查分支是否已存在
        branch_name = f"task/{name}"
        if git.branch_exists(branch_name):
            console.print(f"[red]Error: Branch '{branch_name}' already exists.[/]")
            console.print(
                f"[yellow]Hint: Use different name or 'vibe3 flow switch {name}'[/]"
            )
            raise typer.Exit(1)

        # 创建分支并注册 flow
        try:
            flow = service.create_flow_with_branch(slug=name, start_ref=start_ref)
        except RuntimeError as e:
            console.print(f"[red]Error: {e}[/]")
            raise typer.Exit(1)

        # 绑定 task
        if task:
            try:
                _bind_task_to_flow(branch_name, task, "system", command="flow create")
            except ValueError:
                logger.bind(command="flow create", task=task).warning(
                    "Invalid task ID format, skipping binding"
                )

        # 绑定 spec_ref
        if spec:
            store = SQLiteClient()
            store.update_flow_state(branch_name, spec_ref=spec, latest_actor="system")
            store.add_event(
                branch_name, "spec_bound", "system", detail=f"Spec bound: {spec}"
            )
            logger.bind(command="flow create", spec=spec).info("Spec bound to flow")

        # 自动初始化 handoff current.md
        HandoffService().ensure_current_handoff()

        if json_output:
            typer.echo(json.dumps(flow.model_dump(), indent=2, default=str))
        else:
            render_flow_created(flow, task)
```

**Step 2: 确保移除旧的 new() 函数**

删除或重命名旧的 `new()` 函数（如果还存在）。

### Task 3.3: 更新 flow done 的文档

**文件**：`src/vibe3/commands/flow_lifecycle.py`

**Step 1: 更新 done() 的 docstring**

找到 `done()` 函数，更新文档：

```python
def done(
    branch: Annotated[str | None, typer.Option("--branch", help="Branch name")] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip PR check")] = False,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
) -> None:
    """Close flow, delete branch, and switch to dependent or main.

    This command:
    1. Closes the flow (marks status as 'done')
    2. Deletes the local and remote branch
    3. Switches to dependent branch (if single dependent)
    4. Or switches to main if no/multiple dependents

    For branch chains:
    - Single dependent: Auto-switch to dependent branch
    - Multiple dependents: Prompt with branch list, then switch to main
    - No dependents: Switch to main and pull

    Use --yes to skip PR merge check.
    """
```

---

## Phase 4: 测试验证

### Task 4.1: 测试 get_flow_dependents()

**文件**：`tests/vibe3/clients/test_sqlite_client_dependents.py` (新建)

```python
"""Tests for SQLiteClient.get_flow_dependents()."""

import pytest
from vibe3.clients.sqlite_client import SQLiteClient


class TestGetFlowDependents:
    """Tests for dependency query."""

    def test_no_dependents(self, tmp_path):
        """Branch with no dependents should return empty list."""
        store = SQLiteClient(db_path=tmp_path / "test.db")

        # Setup: feature/A has no dependents
        conn = store._get_connection()
        conn.execute(
            "INSERT INTO flow_state (branch, flow_slug, flow_status, task_issue_number) "
            "VALUES (?, ?, ?, ?)",
            ("feature/A", "feature-a", "active", 123),
        )
        conn.commit()

        dependents = store.get_flow_dependents("feature/A")
        assert dependents == []

    def test_single_dependent(self, tmp_path):
        """Branch with single dependent should return one branch."""
        store = SQLiteClient(db_path=tmp_path / "test.db")

        # Setup: feature/B depends on feature/A
        conn = store._get_connection()
        conn.execute(
            "INSERT INTO flow_state (branch, flow_slug, flow_status, task_issue_number) "
            "VALUES (?, ?, ?, ?)",
            ("feature/A", "feature-a", "active", 123),
        )
        conn.execute(
            "INSERT INTO flow_state (branch, flow_slug, flow_status, task_issue_number) "
            "VALUES (?, ?, ?, ?)",
            ("feature/B", "feature-b", "active", 456),
        )
        conn.execute(
            "INSERT INTO flow_issue_links (branch, issue_number, linked_issue_number, role) "
            "VALUES (?, ?, ?, ?)",
            ("feature/B", 456, 123, "dependency"),
        )
        conn.commit()

        dependents = store.get_flow_dependents("feature/A")
        assert dependents == ["feature/B"]

    def test_multiple_dependents(self, tmp_path):
        """Branch with multiple dependents should return all sorted."""
        store = SQLiteClient(db_path=tmp_path / "test.db")

        # Setup: feature/B and feature/C depend on feature/A
        conn = store._get_connection()
        conn.execute(
            "INSERT INTO flow_state (branch, flow_slug, flow_status, task_issue_number) "
            "VALUES (?, ?, ?, ?)",
            ("feature/A", "feature-a", "active", 123),
        )
        conn.execute(
            "INSERT INTO flow_state (branch, flow_slug, flow_status, task_issue_number) "
            "VALUES (?, ?, ?, ?)",
            ("feature/B", "feature-b", "active", 456),
        )
        conn.execute(
            "INSERT INTO flow_state (branch, flow_slug, flow_status, task_issue_number) "
            "VALUES (?, ?, ?, ?)",
            ("feature/C", "feature-c", "active", 789),
        )
        conn.execute(
            "INSERT INTO flow_issue_links (branch, issue_number, linked_issue_number, role) "
            "VALUES (?, ?, ?, ?)",
            ("feature/B", 456, 123, "dependency"),
        )
        conn.execute(
            "INSERT INTO flow_issue_links (branch, issue_number, linked_issue_number, role) "
            "VALUES (?, ?, ?, ?)",
            ("feature/C", 789, 123, "dependency"),
        )
        conn.commit()

        dependents = store.get_flow_dependents("feature/A")
        assert dependents == ["feature/B", "feature/C"]

    def test_only_active_dependents(self, tmp_path):
        """Should only return active dependents, not done/blocked."""
        store = SQLiteClient(db_path=tmp_path / "test.db")

        conn = store._get_connection()
        conn.execute(
            "INSERT INTO flow_state (branch, flow_slug, flow_status, task_issue_number) "
            "VALUES (?, ?, ?, ?)",
            ("feature/A", "feature-a", "active", 123),
        )
        # Active dependent
        conn.execute(
            "INSERT INTO flow_state (branch, flow_slug, flow_status, task_issue_number) "
            "VALUES (?, ?, ?, ?)",
            ("feature/B", "feature-b", "active", 456),
        )
        # Done dependent (should be excluded)
        conn.execute(
            "INSERT INTO flow_state (branch, flow_slug, flow_status, task_issue_number) "
            "VALUES (?, ?, ?, ?)",
            ("feature/C", "feature-c", "done", 789),
        )
        conn.execute(
            "INSERT INTO flow_issue_links (branch, issue_number, linked_issue_number, role) "
            "VALUES (?, ?, ?, ?)",
            ("feature/B", 456, 123, "dependency"),
        )
        conn.execute(
            "INSERT INTO flow_issue_links (branch, issue_number, linked_issue_number, role) "
            "VALUES (?, ?, ?, ?)",
            ("feature/C", 789, 123, "dependency"),
        )
        conn.commit()

        dependents = store.get_flow_dependents("feature/A")
        assert dependents == ["feature/B"]
```

**运行测试**：

```bash
uv run pytest tests/vibe3/clients/test_sqlite_client_dependents.py -xvs
```

Expected: PASS

### Task 4.2: 测试 flow add 命令

**文件**：`tests/vibe3/commands/test_flow_add.py` (新建)

```python
"""Tests for flow add command."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.models.flow import FlowStatusResponse

runner = CliRunner()


class TestFlowAdd:
    """Tests for flow add command."""

    @patch("vibe3.commands.flow.FlowService")
    @patch("vibe3.commands.flow.GitClient")
    def test_add_flow_to_branch(self, mock_git_class, mock_service_class):
        """Should add flow to current branch."""
        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "feature/test"
        mock_git_class.return_value = mock_git

        mock_service = MagicMock()
        mock_service.get_flow_status.return_value = None
        mock_service.create_flow.return_value = MagicMock(
            flow_slug="test-flow", branch="feature/test"
        )
        mock_service_class.return_value = mock_service

        result = runner.invoke(app, ["flow", "add", "test-flow"])

        assert result.exit_code == 0
        mock_service.create_flow.assert_called_once_with(
            slug="test-flow", branch="feature/test"
        )

    @patch("vibe3.commands.flow.FlowService")
    @patch("vibe3.commands.flow.GitClient")
    def test_add_flow_blocked_by_active(self, mock_git_class, mock_service_class):
        """Should block add on branch with active flow."""
        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "feature/test"
        mock_git_class.return_value = mock_git

        mock_service = MagicMock()
        mock_flow = MagicMock(spec=FlowStatusResponse)
        mock_flow.flow_status = "active"
        mock_flow.flow_slug = "existing-flow"
        mock_service.get_flow_status.return_value = mock_flow
        mock_service_class.return_value = mock_service

        result = runner.invoke(app, ["flow", "add", "new-flow"])

        assert result.exit_code == 1
        assert "already has active flow" in result.output.lower()

    @patch("vibe3.commands.flow.FlowService")
    @patch("vibe3.commands.flow.GitClient")
    def test_add_flow_force_on_active(self, mock_git_class, mock_service_class):
        """Should force add on branch with active flow when --yes."""
        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "feature/test"
        mock_git_class.return_value = mock_git

        mock_service = MagicMock()
        mock_flow = MagicMock(spec=FlowStatusResponse)
        mock_flow.flow_status = "active"
        mock_flow.flow_slug = "existing-flow"
        mock_service.get_flow_status.return_value = mock_flow
        mock_service.create_flow.return_value = MagicMock(
            flow_slug="new-flow", branch="feature/test"
        )
        mock_service_class.return_value = mock_service

        result = runner.invoke(app, ["flow", "add", "new-flow", "--yes"])

        assert result.exit_code == 0
        mock_service.create_flow.assert_called_once()

    @patch("vibe3.commands.flow.FlowService")
    @patch("vibe3.commands.flow.GitClient")
    def test_add_flow_on_done_branch(self, mock_git_class, mock_service_class):
        """Should allow add on branch with done flow with warning."""
        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "feature/test"
        mock_git_class.return_value = mock_git

        mock_service = MagicMock()
        mock_flow = MagicMock(spec=FlowStatusResponse)
        mock_flow.flow_status = "done"
        mock_flow.flow_slug = "old-flow"
        mock_service.get_flow_status.return_value = mock_flow
        mock_service.create_flow.return_value = MagicMock(
            flow_slug="new-flow", branch="feature/test"
        )
        mock_service_class.return_value = mock_service

        result = runner.invoke(app, ["flow", "add", "new-flow"])

        assert result.exit_code == 0
        assert "warning" in result.output.lower()
        mock_service.create_flow.assert_called_once()
```

**运行测试**：

```bash
uv run pytest tests/vibe3/commands/test_flow_add.py -xvs
```

Expected: PASS

### Task 4.3: 测试 flow create 命令

**文件**：`tests/vibe3/commands/test_flow_create.py` (新建)

```python
"""Tests for flow create command."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from vibe3.cli import app

runner = CliRunner()


class TestFlowCreate:
    """Tests for flow create command."""

    @patch("vibe3.commands.flow.FlowService")
    @patch("vibe3.commands.flow.GitClient")
    def test_create_from_main_default(self, mock_git_class, mock_service_class):
        """Should create from main by default."""
        mock_git = MagicMock()
        mock_git.branch_exists.return_value = False
        mock_git_class.return_value = mock_git

        mock_service = MagicMock()
        mock_service.create_flow_with_branch.return_value = MagicMock(
            flow_slug="test", branch="task/test"
        )
        mock_service_class.return_value = mock_service

        result = runner.invoke(app, ["flow", "create", "test"])

        assert result.exit_code == 0
        mock_service.create_flow_with_branch.assert_called_once_with(
            slug="test", start_ref="origin/main"
        )

    @patch("vibe3.commands.flow.FlowService")
    @patch("vibe3.commands.flow.GitClient")
    def test_create_from_current(self, mock_git_class, mock_service_class):
        """Should create from current branch with --base current."""
        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "feature/A"
        mock_git.branch_exists.return_value = False
        mock_git_class.return_value = mock_git

        mock_service = MagicMock()
        mock_service.create_flow_with_branch.return_value = MagicMock(
            flow_slug="test", branch="task/test"
        )
        mock_service_class.return_value = mock_service

        result = runner.invoke(app, ["flow", "create", "test", "--base", "current"])

        assert result.exit_code == 0
        mock_service.create_flow_with_branch.assert_called_once_with(
            slug="test", start_ref="feature/A"
        )

    @patch("vibe3.commands.flow.FlowService")
    @patch("vibe3.commands.flow.GitClient")
    def test_create_from_custom_branch(self, mock_git_class, mock_service_class):
        """Should create from specified branch."""
        mock_git = MagicMock()
        mock_git.branch_exists.return_value = False
        mock_git_class.return_value = mock_git

        mock_service = MagicMock()
        mock_service.create_flow_with_branch.return_value = MagicMock(
            flow_slug="test", branch="task/test"
        )
        mock_service_class.return_value = mock_service

        result = runner.invoke(
            app, ["flow", "create", "test", "--base", "feature/A"]
        )

        assert result.exit_code == 0
        mock_service.create_flow_with_branch.assert_called_once_with(
            slug="test", start_ref="feature/A"
        )

    @patch("vibe3.commands.flow.FlowService")
    @patch("vibe3.commands.flow.GitClient")
    def test_create_branch_exists(self, mock_git_class, mock_service_class):
        """Should error if branch already exists."""
        mock_git = MagicMock()
        mock_git.branch_exists.return_value = True
        mock_git_class.return_value = mock_git

        result = runner.invoke(app, ["flow", "create", "test"])

        assert result.exit_code == 1
        assert "already exists" in result.output.lower()
```

**运行测试**：

```bash
uv run pytest tests/vibe3/commands/test_flow_create.py -xvs
```

Expected: PASS

---

## Phase 5: 文档更新

### Task 5.1: 更新 CLI 帮助文档

**文件**：`src/vibe3/commands/flow.py`

**Step 1: 更新 app 的 help**

```python
app = typer.Typer(
    help=(
        "Manage logic flows (branch-centric: flows are automatically created "
        "and managed based on git branches)\n\n"
        "Commands:\n"
        "  add     Add flow to current branch\n"
        "  create  Create new branch with flow\n"
        "  done    Close flow and delete branch\n"
        "  show    Show flow details\n"
        "  list    List all flows\n"
        "  status  Show flow status\n"
    ),
    no_args_is_help=True,
    rich_markup_mode="rich",
)
```

### Task 5.2: 更新 CLAUDE.md

**文件**：`CLAUDE.md`

在适当位置添加：

```markdown
## Flow 命令体系

**核心命令**：
- `vibe3 flow add <name>` - 在当前分支注册 flow
- `vibe3 flow create <name>` - 创建新分支并注册 flow
- `vibe3 flow done` - 关闭 flow 并自动切换到依赖分支或 main

**分支创建选项**：
- `--base main` (default) - 从 main 创建
- `--base current` - 从当前分支创建
- `--base <branch>` - 从指定分支创建

**依赖管理**：
- 单依赖：flow done 自动切换到依赖分支
- 多依赖：提示分支列表，默认切换到 main
- 无依赖：切换到 main 并 pull
```

---

## Phase 6: 最终验证

### Task 6.1: 运行完整测试

```bash
uv run pytest tests/vibe3/ -q
```

Expected: 全绿（或只允许已知的失败测试）

### Task 6.2: 运行质量检查

```bash
uv run ruff check src/vibe3/
uv run mypy src/vibe3/
```

Expected: PASS

### Task 6.3: 手动验证命令

```bash
# 测试 flow add
vibe3 flow add test-flow

# 测试 flow create
vibe3 flow create test-feature
vibe3 flow create test-feature-2 --base current

# 测试 flow done
vibe3 flow done
```

---

## Deliverables

- [ ] SQLiteClient.get_flow_dependents() 方法实现
- [ ] FlowLifecycleMixin.close_flow() 依赖反查逻辑
- [ ] flow add 命令实现（注册当前分支）
- [ ] flow create 命令实现（创建新分支）
- [ ] 移除旧的 flow new 命令
- [ ] flow done 文档更新
- [ ] 测试覆盖所有新功能
- [ ] 所有测试通过
- [ ] 类型检查通过
- [ ] 代码格式检查通过
- [ ] CLAUDE.md 文档更新

---

## Risks & Mitigations

**风险1**: 用户习惯 flow new
- 缓解: 清晰的错误提示和文档说明

**风险2**: 依赖反查性能
- 缓解: SQL 查询已优化，只查询 active flow

**风险3**: 测试覆盖不足
- 缓解: 完整的测试用例覆盖所有场景

---

## Success Criteria

1. ✅ `flow add` 正确注册 flow 到当前分支
2. ✅ `flow create` 正确创建新分支并注册 flow
3. ✅ `flow done` 正确反查依赖并切换分支
4. ✅ 单依赖自动切换，多依赖提示用户
5. ✅ 所有测试通过
6. ✅ 类型检查通过
7. ✅ 代码格式检查通过
8. ✅ 文档更新完成