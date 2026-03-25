# Flow Done Auto-Switch to Parent Branch Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal**: 改进 `flow done` 命令，使其在关闭当前分支后自动切换到父分支，支持分支链工作流。

**Background**: 当前 `flow done` 只删除分支和标记状态，不会自动切换到父分支。对于分支链 `main → feature/A → refactor/B`，正确的工作流应该是：
1. `refactor/B` done → 自动切换到 `feature/A`
2. `feature/A` done → 自动切换到 `main` 并拉取最新代码

**Tech Stack**: Python 3.10+, Typer, pytest, GitClient

---

## Phase 1: 分析与设计

### Task 1.1: 分析当前实现

**Files:**
- Read: `src/vibe3/services/flow_lifecycle.py`
- Read: `src/vibe3/commands/flow_lifecycle.py`
- Read: `src/vibe3/utils/branch_utils.py`

**Step 1: 理解现有逻辑**

阅读 `close_flow()` 实现，确认：
- 当前只删除分支、标记状态
- 不切换分支
- 不拉取最新代码

**Step 2: 确认需求**

- 关闭分支后自动检测父分支
- 切换到父分支
- 如果父分支是 main/master，自动 pull
- 提供清晰的用户提示

---

## Phase 2: 测试先行（TDD）

### Task 2.1: 为 close_flow 添加失败测试

**Files:**
- Create: `tests/vibe3/services/test_flow_done_auto_switch.py`
- Test: `tests/vibe3/services/test_flow_done_auto_switch.py`

**Step 1: 写失败测试**

覆盖场景：
1. 分支链：`main → feature/A → refactor/B`，关闭 B 后应切换到 A
2. 直接分叉：`main → feature/A`，关闭 A 后应切换到 main
3. main 分支保护：不能关闭 main 分支
4. 自动 pull：切换到 main 后自动拉取最新代码

**测试示例**：
```python
def test_close_flow_switches_to_parent_branch():
    """Close flow should switch to parent branch."""
    # Setup: main → feature/A → refactor/B
    # Current: refactor/B
    # Close: refactor/B
    # Expected: switched to feature/A
    pass

def test_close_flow_switches_to_main_and_pulls():
    """Close flow on main child should switch to main and pull."""
    # Setup: main → feature/A
    # Current: feature/A
    # Close: feature/A
    # Expected: switched to main and pulled
    pass
```

**Step 2: 运行确认失败**

Run: `uv run pytest tests/vibe3/services/test_flow_done_auto_switch.py -q`
Expected: FAIL (功能未实现)

---

## Phase 3: 核心实现

### Task 3.1: 实现自动切换逻辑

**Files:**
- Modify: `src/vibe3/services/flow_lifecycle.py`
- Modify: `src/vibe3/commands/flow_lifecycle.py`
- Test: `tests/vibe3/services/test_flow_done_auto_switch.py`

**Step 1: 修改 close_flow 服务层**

在 `FlowLifecycleMixin.close_flow()` 中添加：
```python
def close_flow(self: Any, branch: str, check_pr: bool = True) -> None:
    # ... 现有逻辑：删除分支、标记状态 ...

    # 新增：切换到父分支
    from vibe3.utils.branch_utils import find_parent_branch

    parent = find_parent_branch(branch)
    if parent:
        git.switch_branch(parent)
        logger.bind(
            domain="flow",
            action="close",
            branch=branch,
            parent=parent,
        ).info("Switched to parent branch")

        # 如果是 main，拉取最新代码
        if parent in ["main", "origin/main", "master", "origin/master"]:
            try:
                git._run(["pull"])
                logger.info("Pulled latest changes on main")
            except Exception as e:
                logger.warning(f"Failed to pull: {e}")
```

**Step 2: 修改命令层输出**

在 `flow_lifecycle.py` 的 `done()` 中更新提示信息：
```python
def done(...):
    # ... 现有逻辑 ...

    # 获取父分支信息
    from vibe3.utils.branch_utils import find_parent_branch
    parent = find_parent_branch(target_branch)

    if parent:
        typer.echo(f"Flow closed, switched to parent branch: {parent}")
        if parent in ["main", "origin/main", "master", "origin/master"]:
            typer.echo("Pulled latest changes")
    else:
        typer.echo(f"Flow closed, branch '{target_branch}' deleted")
```

**Step 3: 跑测试**

Run: `uv run pytest tests/vibe3/services/test_flow_done_auto_switch.py -xvs`
Expected: PASS

**Step 4: 运行全量测试**

Run: `uv run pytest tests/vibe3/ -q`
Expected: 全绿

---

## Phase 4: 边界情况处理

### Task 4.1: 处理特殊情况

**Files:**
- Modify: `src/vibe3/services/flow_lifecycle.py`
- Test: `tests/vibe3/services/test_flow_done_auto_switch.py`

**Step 1: 处理找不到父分支的情况**

```python
# 如果找不到父分支，保持在当前分支（通常是 main）
if not parent:
    logger.warning("No parent branch found, staying on current branch")
    return
```

**Step 2: 处理 main 分支保护**

确保不能对 main 分支执行 `flow done`：
```python
if branch in ["main", "master"]:
    raise RuntimeError("Cannot close main/master branch")
```

**Step 3: 处理父分支不存在的情况**

```python
if parent and not git.branch_exists(parent):
    logger.warning(f"Parent branch {parent} not found, staying on current branch")
    # 尝试切换到 main
    if git.branch_exists("main"):
        git.switch_branch("main")
    elif git.branch_exists("master"):
        git.switch_branch("master")
```

**Step 4: 跑测试验证**

Run: `uv run pytest tests/vibe3/services/test_flow_done_auto_switch.py -xvs`
Expected: PASS

---

## Phase 5: 文档和验证

### Task 5.1: 更新文档

**Files:**
- Modify: `src/vibe3/commands/flow_lifecycle.py` (docstring)
- Modify: `README.md` (if exists)

**Step 1: 更新命令文档**

```python
def done(...):
    """Close flow, delete branch, and switch to parent branch.

    This command:
    1. Closes the flow (marks status as 'done')
    2. Deletes the local and remote branch
    3. Auto-detects and switches to the parent branch
    4. Pulls latest changes if parent is main/master

    For branch chains like: main → feature/A → refactor/B
    - Close refactor/B: switches to feature/A
    - Close feature/A: switches to main and pulls

    Use --yes to skip PR merge check.
    """
```

**Step 2: 添加使用示例**

在 README 或文档中添加：
```markdown
## Branch Chain Workflow

Vibe supports branch chains (main → feature/A → refactor/B):

1. `vibe review base` auto-detects parent (refactor/B vs feature/A)
2. `vibe flow done` auto-switches to parent (refactor/B → feature/A)
3. Continue until back to main with latest code
```

---

## Final Gate: 验证

### Task F.1: 手动验证

**Step 1: 创建测试分支链**

```bash
# 在 main 创建 feature/A
git checkout -b feature/A
# 做一些提交...

# 在 feature/A 创建 refactor/B
git checkout -b refactor/B
# 做一些提交...
```

**Step 2: 测试 flow done**

```bash
# 当前在 refactor/B
vibe flow done

# 应该：
# 1. 关闭 refactor/B
# 2. 切换到 feature/A
# 3. 提示："Switched to parent branch: feature/A"
```

**Step 3: 继续关闭**

```bash
# 当前在 feature/A
vibe flow done

# 应该：
# 1. 关闭 feature/A
# 2. 切换到 main
# 3. 拉取最新代码
# 4. 提示："Switched to parent branch: main, pulled latest changes"
```

### Task F.2: 自动化测试

**Step 1: 运行质量检查**

```bash
uv run ruff check src/vibe3
uv run mypy src/vibe3
uv run pytest tests/vibe3/ -q
```

**Step 2: 检查 LOC**

```bash
vibe3 inspect metrics
```

Expected: Python LOC ≤ 20000

---

## Deliverables

- [x] `close_flow()` 自动切换到父分支
- [x] main/master 自动 pull 最新代码
- [x] 清晰的用户提示信息
- [x] 完整的测试覆盖
- [x] 更新的文档

---

## Risks & Mitigations

**风险1**: 找不到父分支
- 缓解: 保持在当前分支，给用户警告

**风险2**: 父分支已被删除
- 缓解: 尝试切换到 main，如果失败则保持在当前分支

**风险3**: pull 失败（网络问题）
- 缓解: 记录警告，不中断流程

---

## Success Criteria

1. ✅ 关闭 `refactor/B` 后自动切换到 `feature/A`
2. ✅ 关闭 `feature/A` 后自动切换到 `main` 并 pull
3. ✅ 所有测试通过
4. ✅ Python LOC ≤ 20000
5. ✅ 用户提示清晰明确