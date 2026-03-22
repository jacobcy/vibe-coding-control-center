---
document_type: plan
title: Flow 状态转换命令迁移 (V2 → V3)
status: draft
author: Claude Sonnet 4.6
created: 2026-03-23
last_updated: 2026-03-23
related_docs:
  - docs/v3/handoff/02-flow-task-foundation.md
  - docs/v3/task-flow-guide.md
  - docs/standards/vibe3-command-standard.md
---

# Flow 状态转换命令迁移 (V2 → V3)

**Goal**: 将 V2 Shell 实现的 flow 生命周期命令迁移到 V3 Python，实现完整的分支管理与状态同步。

## 1. 背景

### 当前状态

| 命令 | V2 (Shell) | V3 (Python) | 差距 |
|------|------------|-------------|------|
| `flow new` | 创建分支 + 数据库记录 | 仅数据库记录 | ❌ 缺少分支创建 |
| `flow switch` | 暂存/恢复 + 切换分支 | ❌ 未实现 | 完全缺失 |
| `flow done` | 删除分支 + 标记结束 | ❌ 未实现 | 完全缺失 |
| `flow blocked` | 标记 blocked | ❌ 未实现 | 完全缺失 |
| `flow aborted` | 标记废弃 + 删除分支 | ❌ 未实现 | 完全缺失 |

### 设计原则：actor 参数

**actor 字段的初衷**：记录 agent 阶段交接的责任人（上下文传递链）。

**使用规则**：
- ✅ **保留**：handoff 命令（plan/report/audit/append）- 用于 agent 间交接
- ❌ **移除**：flow/task 命令 - 纯业务逻辑，不需要记录 actor

**当前问题**：
- `flow new/bind` 有 actor 参数 ❌ 应该移除
- `task link/status` 有 actor 参数 ❌ 应该移除
- `handoff plan/report/audit/append` 有 actor 参数 ✅ 保留

**清理范围**：
1. 移除 `flow new` 的 actor 参数
2. 移除 `flow bind` 的 actor 参数
3. 移除 `task link` 的 actor 参数
4. 移除 `task status` 的 actor 参数
5. Service 层签名更新：不接收 actor 参数，内部逻辑可保留 latest_actor 字段

### V2 核心语义

```
flow new <name> [--branch <ref>] [--save-unstash]
  → git checkout -b <branch> <ref>
  → 更新 flow_state / worktrees.json

flow switch <name>
  → stash 当前改动
  → git checkout <branch>
  → 恢复 stash

flow done [--branch <ref>]
  → 检查 PR merged
  → 删除本地/远程分支
  → 标记 flow_status = done

flow blocked
  → 标记 flow_status = blocked
  → 保留分支

flow aborted
  → 标记 flow_status = aborted
  → 删除分支
```

## 2. 实现计划

### Phase 1: GitClient 增强

**文件**: `src/vibe3/clients/git_client.py`

新增方法：

```python
def create_branch(self, branch_name: str, start_ref: str = "origin/main") -> None:
    """Create a new branch from start_ref."""

def switch_branch(self, branch_name: str) -> None:
    """Switch to existing branch."""

def delete_branch(self, branch_name: str, force: bool = False) -> None:
    """Delete local branch."""

def delete_remote_branch(self, branch_name: str) -> None:
    """Delete remote branch."""

def stash_push(self, message: str | None = None) -> str:
    """Stash current changes, return stash ref."""

def stash_apply(self, stash_ref: str) -> None:
    """Apply and drop stash."""

def has_uncommitted_changes(self) -> bool:
    """Check if working directory is dirty."""

def branch_exists(self, branch_name: str) -> bool:
    """Check if branch exists (local or remote)."""
```

### Phase 2: FlowService 增强

**文件**: `src/vibe3/services/flow_service.py`

新增方法：

```python
def create_flow_with_branch(
    self,
    slug: str,
    start_ref: str = "origin/main",
    save_unstash: bool = False,
    actor: str = "unknown",
) -> FlowState:
    """
    创建新 flow 并创建分支。

    1. 检查分支是否已存在
    2. 检查工作目录是否干净（或 save_unstash）
    3. stash 当前改动（如果 save_unstash）
    4. git checkout -b <branch> <start_ref>
    5. 更新 flow_state
    6. 恢复 stash（如果有）
    """

def switch_flow(
    self,
    target: str,
    actor: str = "unknown",
) -> FlowState:
    """
    切换到已有 flow。

    1. 检查目标分支是否存在
    2. stash 当前改动
    3. git checkout <branch>
    4. 恢复 stash
    5. 更新 worktrees.json（可选）
    """

def close_flow(
    self,
    branch: str,
    actor: str = "unknown",
    check_pr: bool = True,
) -> None:
    """
    关闭 flow 并删除分支。

    1. 检查 PR 是否已 merge
    2. 如果未 merge，检查是否有 review evidence
    3. 删除本地分支
    4. 删除远程分支（如果存在）
    5. 标记 flow_status = done
    """

def block_flow(
    self,
    branch: str,
    reason: str,
    actor: str = "unknown",
) -> None:
    """
    标记 flow 为 blocked。

    1. 更新 flow_status = blocked
    2. 记录 blocked_by
    3. 添加事件
    4. 保留分支
    """

def abort_flow(
    self,
    branch: str,
    actor: str = "unknown",
) -> None:
    """
    废弃 flow 并删除分支。

    1. 更新 flow_status = aborted
    2. 删除本地分支
    3. 删除远程分支（如果存在）
    4. 添加事件
    """
```

### Phase 3: Command Layer 实现

**文件**: `src/vibe3/commands/flow.py`

**设计原则**：
- `actor` 参数仅在 handoff 命令中使用（plan/report/audit），用于记录阶段交接的责任人
- flow 生命周期命令（new/switch/done/blocked/aborted）不需要 actor 参数
- service 层的 `latest_actor` 字段保留，但不再从命令层传入，改为内部逻辑处理

更新命令实现：

```python
@app.command()
def new(
    name: Annotated[str | None, typer.Argument()] = None,
    issue: Annotated[str | None, typer.Option("--issue")] = None,
    branch: Annotated[str, typer.Option("--branch", help="Start ref")] = "origin/main",
    save_unstash: Annotated[bool, typer.Option("--save-unstash")] = False,
    trace: Annotated[bool, typer.Option()] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Create a new flow with branch."""
    # ... 调用 service.create_flow_with_branch()

@app.command()
def switch(
    target: Annotated[str, typer.Argument()],
    trace: Annotated[bool, typer.Option()] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Switch to existing flow."""
    # ... 调用 service.switch_flow()

@app.command()
def done(
    branch: Annotated[str | None, typer.Option("--branch")] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip PR check")] = False,
    trace: Annotated[bool, typer.Option()] = False,
) -> None:
    """Close flow and delete branch."""
    # ... 调用 service.close_flow()

@app.command()
def blocked(
    branch: Annotated[str | None, typer.Option("--branch")] = None,
    reason: Annotated[str, typer.Option("--reason")] = "",
    trace: Annotated[bool, typer.Option()] = False,
) -> None:
    """Mark flow as blocked."""
    # ... 调用 service.block_flow()

@app.command()
def aborted(
    branch: Annotated[str | None, typer.Option("--branch")] = None,
    trace: Annotated[bool, typer.Option()] = False,
) -> None:
    """Abort flow and delete branch."""
    # ... 调用 service.abort_flow()
```

**注意**：需要清理现有命令中的 actor 参数：
- `flow new` - 移除 actor 参数
- `flow bind` - 移除 actor 参数
- `task link` - 移除 actor 参数（待讨论）
- `task status` - 移除 actor 参数（待讨论）

## 3. 实现顺序

### Step 0: 清理 actor 参数 (Day 0)

**目标**：移除 flow/task 命令中不必要的 actor 参数。

**文件变更**：

1. `src/vibe3/commands/flow.py`
   - `flow new` - 移除 actor 参数
   - `flow bind` - 移除 actor 参数

2. `src/vibe3/commands/task.py`
   - `task link` - 移除 actor 参数
   - `task status` - 移除 actor 参数

3. `src/vibe3/services/flow_service.py`
   - `create_flow` - 移除 actor 参数
   - Service 内部不更新 latest_actor（或使用固定值如 "system"）

4. `src/vibe3/services/task_service.py`
   - `link_issue` - 移除 actor 参数
   - `update_flow_status` - 移除 actor 参数
   - Service 内部不更新 latest_actor（或使用固定值如 "system"）

**测试**：
- 确保命令仍能正常执行
- 验证 flow_state 表的 latest_actor 字段不再从命令层接收值

### Step 1: GitClient 基础方法 (Day 1)

1. 实现 `create_branch`, `switch_branch`, `delete_branch`
2. 实现 `stash_push`, `stash_apply`
3. 实现 `has_uncommitted_changes`, `branch_exists`
4. 单元测试

### Step 2: FlowService 核心逻辑 (Day 2-3)

1. 实现 `create_flow_with_branch`
   - 分支存在检查
   - dirty worktree 检查
   - stash/restore 逻辑
2. 实现 `switch_flow`
3. 单元测试

**方法签名**（无 actor 参数）：

```python
def create_flow_with_branch(
    self,
    slug: str,
    start_ref: str = "origin/main",
    save_unstash: bool = False,
) -> FlowState:
    """创建新 flow 并创建分支。"""

def switch_flow(self, target: str) -> FlowState:
    """切换到已有 flow。"""
```

### Step 3: FlowService 关闭逻辑 (Day 4-5)

1. 实现 `close_flow`
   - PR merged 检查
   - review evidence 检查（可选）
   - 分支删除
2. 实现 `block_flow`
3. 实现 `abort_flow`
4. 单元测试

**方法签名**（无 actor 参数）：

```python
def close_flow(
    self,
    branch: str,
    check_pr: bool = True,
) -> None:
    """关闭 flow 并删除分支。"""

def block_flow(self, branch: str, reason: str) -> None:
    """标记 flow 为 blocked。"""

def abort_flow(self, branch: str) -> None:
    """废弃 flow 并删除分支。"""
```

### Step 4: Command Layer (Day 6)

1. 更新 `flow new` 命令
2. 实现 `flow switch` 命令
3. 实现 `flow done` 命令
4. 实现 `flow blocked` 命令
5. 实现 `flow aborted` 命令
6. 集成测试

### Step 5: 文档更新 (Day 7)

1. 更新 [task-flow-guide.md](../../v3/task-flow-guide.md)
2. 更新帮助文档
3. 验收测试

## 4. 测试策略

### 单元测试

```python
# tests/vibe3/unit/test_git_client.py
def test_create_branch():
    """测试分支创建"""

def test_stash_push_apply():
    """测试 stash 保存和恢复"""

# tests/vibe3/unit/test_flow_service.py
def test_create_flow_with_branch():
    """测试创建 flow 并创建分支"""

def test_create_flow_already_exists():
    """测试分支已存在时报错"""

def test_create_flow_dirty_worktree():
    """测试 dirty worktree 检查"""

def test_switch_flow():
    """测试切换 flow"""

def test_close_flow():
    """测试关闭 flow"""

def test_block_flow():
    """测试标记 blocked"""

def test_abort_flow():
    """测试废弃 flow"""
```

### 集成测试

```python
# tests/vibe3/integration/test_flow_lifecycle.py
def test_flow_new_switch_done_lifecycle():
    """
    完整生命周期测试：
    1. flow new feature-a
    2. 做一些修改
    3. flow switch feature-b
    4. flow switch feature-a
    5. flow done feature-a
    """
```

## 5. 验收标准

### 功能验收

- [ ] `vibe3 flow new feature-a` 创建分支 `task/feature-a` 并记录 flow_state
- [ ] `vibe3 flow new feature-b --save-unstash` 把当前改动带入新分支
- [ ] `vibe3 flow switch feature-a` 切换到已有 flow
- [ ] `vibe3 flow done` 删除分支并标记 flow_status = done
- [ ] `vibe3 flow blocked --reason "等待依赖"` 标记 blocked
- [ ] `vibe3 flow aborted` 标记废弃并删除分支

### Actor 参数清理验收

- [ ] `flow new` 无 actor 参数，命令正常执行
- [ ] `flow bind` 无 actor 参数，命令正常执行
- [ ] `task link` 无 actor 参数，命令正常执行
- [ ] `task status` 无 actor 参数，命令正常执行
- [ ] `handoff plan/report/audit/append` 保留 actor 参数，正常执行

### 错误处理验收

- [ ] 分支已存在时 `flow new` 报错
- [ ] dirty worktree 时 `flow new` 提示使用 `--save-unstash`
- [ ] 切换到不存在的 flow 时 `flow switch` 报错
- [ ] PR 未 merge 时 `flow done` 提示（除非 `--yes`）

### 代码质量验收

- [ ] `mypy --strict` 检查通过
- [ ] 所有新增文件 < 300 行
- [ ] 单元测试覆盖率 > 80%
- [ ] 遵循 [python-standards.md](../../../.agent/rules/python-standards.md)

## 6. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| stash 冲突 | 用户改动丢失 | 提供详细的冲突解决指南 |
| PR merged 检测失败 | 分支误删 | 增加 `--yes` 选项作为安全网 |
| 远程分支删除失败 | 残留分支 | 继续删除本地分支，记录错误日志 |

## 7. 后续工作

- [ ] `flow status` 显示 blocked/aborted 状态
- [ ] `flow list --status blocked` 过滤
- [ ] 与 GitHub PR 深度集成（自动 merge）
- [ ] 与 review evidence 集成

## 8. 参考

- V2 实现：
  - `lib/flow.sh` - new/switch 入口
  - `lib/flow_runtime.sh` - stash/restore 逻辑
  - `lib/flow_done.sh` - done 关闭逻辑
- 标准文档：
  - [docs/standards/vibe3-command-standard.md](../../standards/vibe3-command-standard.md)
  - [docs/v3/task-flow-guide.md](../../v3/task-flow-guide.md)