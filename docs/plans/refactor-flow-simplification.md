# Plan: Flow 系统简化 — 去除 branch 主动管理层

**状态**: Ready
**实施分支**: refactor/flow-simplification
**目标**: 删除 flow create/done 及其 git 操作包装层，不影响主干

---

## Summary

Flow 系统现在混合了两个职责：

- **被动跟踪**（正确）：记录 branch ↔ issue ↔ event 关系
- **主动管理**（错误）：创建/删除 branch 和 worktree

实施路径：**保留被动跟踪，删除主动管理**。主干（plan/run/review/handoff/orchestra）全程不中断。

每个 Step 独立提交，失败可单步 revert。

---

## 目标状态

### 用户工作流（简化后）

```
git checkout -b task/issue-<N>     # 唯一的分支操作，git 原生
vibe3 flow show                    # 自动注册 + 显示状态（含 parent branch）
vibe3 flow bind <issue>            # 绑定 issue（可选，orchestra 自动绑）
vibe3 plan                         # 根据 issue 描述创建 plan
vibe3 run                          # 根据 plan 执行
vibe3 review                       # 根据 plan 总结
vibe3 handoff show                 # 查看 agent 运行记录
vibe3 check --fix --all            # 自动清理已 merged PR 的 flow（已有能力，整合即可）
```

orchestra/AssigneeDispatchService 保持不变，自动调度上述流程。

### `vibe3 flow show` 目标输出

```
branch: task/issue-42
parent: main
flow_slug: issue-42
status: active
task: #42  "Add dark mode support"
pr: #123   state=open   url=...
events:
  2026-03-31 10:00  plan_created   planner/sonnet
  2026-03-31 10:15  run_started    executor/sonnet
  2026-03-31 11:20  review_done    reviewer/sonnet
```

新增 `parent: main` 行，记录该 branch 是从哪个 branch checkout 出来的，方便：
- `flow status` 显示依赖树
- 快速回到上一个 branch

---

## 保留 vs 删除

### 保留（主干）

| 组件 | 原因 |
|------|------|
| `ensure_flow_for_current_branch()` | 被动注册，`plan/run/review` 都依赖 |
| `FlowService.create_flow()` | orchestra 调用（无 branch 操作） |
| `FlowService.get_current_branch()` | 所有命令依赖 |
| `FlowService.ensure_flow_for_branch()` | 被动注册核心，**扩展：同时记录 parent_branch** |
| `FlowService.block_flow()` | 还有用 |
| `flow add` 命令 | 显式注册当前 branch |
| `flow bind` 命令 | 绑定 issue |
| `flow show/status/list` 命令 | 状态查看，**扩展：显示 parent_branch** |
| `flow blocked` 命令 | 标记阻塞 |
| `handoff` 全部 | agent 链路记录，不变 |
| `orchestra/*` 全部 | 自动调度，不变 |
| `check --fix --all` | **整合为 flow prune 的实现基础**，不新增重复逻辑 |
| `TaskService.link_issue()` | bind 的底层，保留 |

### 删除

| 文件/组件 | 行数 | 原因 |
|-----------|------|------|
| `services/flow_usecase.py` | 277 | 全部是 flow create 的 worktree governance |
| `services/flow_close_ops.py` | 373 | 全部是 flow done 的 branch/worktree 删除 |
| `services/flow_create_decision.py` | ~80 | 仅被 FlowUsecase 使用 |
| `services/base_resolution_usecase.py` | ~100 | 仅被 FlowUsecase 使用 |
| `services/flow_lifecycle.py` 部分 | ~50 | 删 close_flow/abort_flow，保留 block_flow |
| `FlowService.create_flow_with_branch()` | ~45 | git 的工作 |
| `FlowService.switch_flow()` | ~25 | 等于 `git checkout` |
| `commands/flow.py` `create`/`new` 函数 | ~80 | 删除 |
| `commands/flow_lifecycle.py` `done`/`aborted`/`switch` | ~120 | 删除 |
| `clients/github_project_*.py`（3 个文件） | ~750 | Project 是展示层，非主干 |
| **合计** | **~1900 行** | |

### 新增（净增约 80 行）

| 组件 | 行数 | 说明 |
|------|------|------|
| `flow_state.parent_branch` 列 | ~20 | SQLite migration，记录 parent branch |
| `GitClient.get_parent_branch()` | ~20 | 用 git reflog 推断 parent branch |
| `ensure_flow_for_branch()` 扩展 | ~10 | 注册时记录 parent_branch |
| `flow prune` 命令 | ~30 | 调用 `CheckService.auto_fix()` 实现，不重复逻辑 |

---

## 实现步骤

步骤按"保护主干"原则排序：先加能力，再删旧代码，全程可回滚。

### Step 1：验证被动注册路径（无代码改动）

确认 `ensure_flow_for_current_branch()` 已能支撑主干，不需要 `flow create`：

```bash
git checkout -b test/flow-passive-verify
uv run python src/vibe3/cli.py flow show    # 应自动注册并显示
uv run python src/vibe3/cli.py flow bind 1  # 应能绑定 issue
git checkout -
git branch -d test/flow-passive-verify
```

预期：`flow show` 自动注册，无需 `flow create`。**验证通过后继续。**

---

### Step 2：新增 parent_branch 跟踪

**a. SQLite migration** — `clients/sqlite_schema.py`

在 `init_schema()` 的 migration 段新增：
```python
if "parent_branch" not in existing:
    cursor.execute("ALTER TABLE flow_state ADD COLUMN parent_branch TEXT")
```

**b. 推断 parent branch** — `clients/git_branch_ops.py` 新增函数：
```python
def get_parent_branch(current_branch: str) -> str | None:
    """从 git reflog 推断当前 branch 的来源 branch。

    查找最近一条 "checkout: moving from X to current_branch" 记录，
    返回 X（来源 branch 名），未找到返回 None。
    """
    try:
        output = _run_git(["reflog", "--format=%gs"])
        pattern = f"checkout: moving from (.+) to {re.escape(current_branch)}"
        for line in output.splitlines():
            m = re.search(pattern, line)
            if m:
                return m.group(1)
    except GitError:
        pass
    return None
```

同步在 `GitClient` 暴露该方法。

**c. 注册时记录** — `services/flow_service.py` 的 `ensure_flow_for_branch()` / `create_flow()`：
```python
parent = self.git_client.get_parent_branch(branch)
self.store.update_flow_state(branch, parent_branch=parent)
```

**d. flow show 显示** — `commands/flow_status.py` 或 `commands/handoff_read.py`：
在输出中追加 `parent: <parent_branch>` 行（若存在）。

**验证**：
```bash
git checkout -b test/parent-tracking
uv run python src/vibe3/cli.py flow show  # 应显示 parent: <来源branch>
git checkout -
git branch -d test/parent-tracking
uv run pytest tests/vibe3/ -k "parent_branch or flow_show"
uv run mypy src/vibe3
```

---

### Step 3：新增 `flow prune` 命令（复用 check 能力）

`check --fix --all` 已实现"检测 PR merged → 标记 flow done"的逻辑（`CheckService._mark_flow_done()`）。
`flow prune` 不重复实现，直接委托：

**实现位置**：`commands/flow.py` 新增：

```python
@app.command()
def prune(
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    """Auto-close flows where PR is merged or issue is closed.

    Delegates to CheckService.run_all_checks(fix=True) — same logic as
    `vibe3 check --fix --all`, surfaced as a flow-level command.
    """
    from vibe3.services.check_service import CheckService
    results = CheckService().run_all_checks(fix=not dry_run)
    closed = [r for r in results if r.is_valid and r.branch]
    for r in closed:
        status = "would close" if dry_run else "closed"
        console.print(f"  {status}: {r.branch}")
    if not closed:
        console.print("No stale flows found.")
```

**验证**：
```bash
uv run python src/vibe3/cli.py flow prune --dry-run
uv run pytest tests/vibe3/ -k "prune or check"
```

---

### Step 4：内联 `bind` 命令的 FlowUsecase 依赖

`flow bind` 用了 `FlowUsecase.validate_issue_refs()`（15 行静态方法）和 `FlowUsecase.bind_issue()`（3 行）。直接内联，移除 FlowUsecase 依赖：

```python
# commands/flow.py bind() 改为直接调用：
branch = FlowService().get_current_branch()
issue_number = parse_issue_number(issue)
TaskService().link_issue(branch, issue_number, role, actor=None)
```

**验证**：
```bash
uv run python src/vibe3/cli.py flow bind 42
uv run pytest tests/vibe3/ -k "bind"
uv run mypy src/vibe3
```

---

### Step 5：删除 `flow create` / `flow new` 命令

`commands/flow.py`：
- 删除 `create()` 函数（~80 行）及其所有参数定义
- 删除 `new()` 函数（~15 行，已 deprecated）
- 删除 `FlowUsecase` import（此时已无引用）

`commands/command_options.py`：
```python
# 改前
typer.echo("  vibe3 flow create <name>", err=True)
# 改后
typer.echo("  git checkout -b <branch-name>", err=True)
```

**验证**：
```bash
uv run python src/vibe3/cli.py flow --help  # 不出现 create
uv run pytest tests/vibe3/ -x
uv run mypy src/vibe3
```

---

### Step 6：删除 `flow done` / `flow aborted` / `flow switch` 命令

`commands/flow_lifecycle.py`：
- 删除 `done()` 函数
- 删除 `aborted()` 函数
- 删除 `switch()` 函数
- 保留 `blocked()` 函数

从 `commands/flow.py` 的注册行中同步移除：
```python
# 删除这三行
app.command(name="done")(done)
app.command(name="aborted")(aborted)
app.command(name="switch")(switch)
```

**验证**：
```bash
uv run python src/vibe3/cli.py flow --help  # 不出现 done/aborted/switch
uv run pytest tests/vibe3/ -x
```

---

### Step 7：删除 FlowService 的 git 操作方法

`services/flow_service.py`：
- 删除 `create_flow_with_branch()`
- 删除 `switch_flow()`
- 删除 `close_flow()` 委托

`services/flow_lifecycle.py`：
- 删除 `FlowLifecycleMixin.close_flow()`
- 删除 `FlowLifecycleMixin.abort_flow()`
- 删除 `_abort_flow_impl()`
- 保留 `block_flow()` 和 `_block_flow_impl()`

**验证**：
```bash
uv run mypy src/vibe3
uv run pytest tests/vibe3/ -x
```

---

### Step 8：删除死代码文件

先确认零引用：
```bash
uv run python src/vibe3/cli.py inspect symbols src/vibe3/services/flow_usecase.py
uv run python src/vibe3/cli.py inspect symbols src/vibe3/services/flow_close_ops.py
uv run python src/vibe3/cli.py inspect symbols src/vibe3/services/flow_create_decision.py
uv run python src/vibe3/cli.py inspect symbols src/vibe3/services/base_resolution_usecase.py
```

确认后删除（~830 行）。

**验证**：
```bash
uv run mypy src/vibe3
uv run ruff check src/vibe3
uv run pytest tests/vibe3/ -x
```

---

### Step 9：删除 GitHub Project 集成

先确认引用范围：
```bash
grep -rn "GitHubProjectClient\|github_project" src/vibe3/ --include="*.py" | grep -v test_
```

删除：
- `clients/github_project_client.py`
- `clients/github_project_mutation_ops.py`
- `clients/github_project_query_ops.py`
- 从 `services/task_bridge_mutation.py` 和 `services/task_service.py` 移除 Project 相关调用

**验证**：
```bash
uv run pytest tests/vibe3/ -x
uv run mypy src/vibe3
```

---

### Step 10：更新 Skills 文档

- `skills/vibe-done/SKILL.md`：
  - 删除 `vibe3 flow done` 调用
  - 替换为：`gh pr merge <N>`（GitHub 完成）+ `vibe3 flow prune`（清理记录）
- `skills/vibe-new/SKILL.md`：
  - 删除"场景A：`vibe3 flow create <name> --task <issue> --base main`"
  - 替换为：`git checkout -b task/issue-<N>`（新建）或 `vibe3 flow add`（注册已有 branch）
- `skills/vibe-instruction/SKILL.md`：
  - 删除 `flow create` 示例行
- `skills/vibe-start/SKILL.md`：检查 `flow add` 用法，确认无需改动

---

## 风险与回滚

| 风险 | 可能性 | 缓解 |
|------|--------|------|
| orchestra 依赖 `close_flow` | 低 | `FlowOrchestrator` 只用 `create_flow()`（无 branch 操作），已确认 |
| 测试 mock 了 `FlowUsecase` | 中 | Step 8 前先跑 `pytest -x`，零失败再删 |
| `task_service` 依赖 Project client | 中 | Step 9 前 inspect symbols 确认 |
| `get_parent_branch` reflog 为空 | 低 | 返回 None，`flow show` 不显示该行，不报错 |
| skills 引用了删掉的命令 | 低 | Step 10 同步更新，skills 不跑 CI |

**回滚**：每 Step 独立 commit，失败 `git revert <sha>`。

---

## 验收标准

执行完所有步骤后，全部通过即为完成：

```bash
# 1. 被动注册
git checkout -b test/verify-simplified
uv run python src/vibe3/cli.py flow show
# 预期：自动注册，显示 branch / parent / pr / events

# 2. 绑定 issue
uv run python src/vibe3/cli.py flow bind 42
uv run python src/vibe3/cli.py flow show
# 预期：task: #42

# 3. parent branch 显示
# 预期：parent: main（或来源 branch）

# 4. prune
uv run python src/vibe3/cli.py flow prune --dry-run
# 预期：无报错，扫描所有 active flow

# 5. 主干命令正常
uv run python src/vibe3/cli.py plan --help
uv run python src/vibe3/cli.py run --help
uv run python src/vibe3/cli.py review --help

# 6. flow create/done 不再存在
uv run python src/vibe3/cli.py flow --help
# 预期：无 create / done / switch / aborted

# 7. 全量测试
uv run pytest tests/vibe3/ -x
uv run mypy src/vibe3
uv run ruff check src/vibe3

# 清理
git checkout -
git branch -d test/verify-simplified
```
