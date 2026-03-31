# Plan: Flow 系统简化 — 去除 branch 主动管理层

**状态**: Ready
**实施分支**: refactor/flow-simplification
**Issue**: #391
**目标**: 删除 flow create/done 及其 git 操作包装层，不影响主干

---

## Summary

Flow 系统现在混合了两个职责：

- **被动跟踪**（正确）：记录 branch ↔ issue ↔ event 关系
- **主动管理**（错误）：创建/删除 branch 和 worktree

实施路径：**保留被动跟踪，删除主动管理**。主干（plan/run/review/handoff/orchestra）全程不中断。

每个 Step 独立提交，失败可单步 revert。

---

## 已有能力（不需要新建）

| 能力 | 现有位置 | 状态 |
|------|----------|------|
| parent branch 推断 | `utils/branch_utils.find_parent_branch()` | 已实现，未在 flow show 展示 |
| PR merged → 标记 flow done | `check_service._check_branch()` + `_mark_flow_done()` | 已实现，`check --fix --all` 调用 |
| 被动注册 branch 为 flow | `ensure_flow_for_current_branch()` | 已实现，所有命令已用 |

---

## 目标状态

### 用户工作流（简化后）

```
git checkout -b task/issue-<N>     # 唯一的分支操作，git 原生
vibe3 flow show                    # 自动注册 + 显示状态（含 parent branch）
vibe3 flow status                  # 自动标记 merged PR 为 done，再列出活跃 flow
vibe3 flow bind <issue>            # 绑定 issue
vibe3 plan                         # 根据 issue 描述创建 plan
vibe3 run                          # 根据 plan 执行
vibe3 review                       # 根据 plan 总结
vibe3 handoff show                 # 查看 agent 运行记录
vibe3 check --fix --all            # 完整健康检查（已有，不改动）
```

### `vibe3 flow show` 目标输出

```
branch: task/issue-42
parent: main                        # 新增：从 find_parent_branch() 读取
flow_slug: issue-42
status: active
task: #42  "Add dark mode support"
pr: #123   state=open
events:
  2026-03-31 10:00  plan_created   planner/sonnet
  2026-03-31 10:15  run_started    executor/sonnet
  2026-03-31 11:20  review_done    reviewer/sonnet
```

### `vibe3 flow status` 行为变化

执行前先调用 `CheckService().verify_all_flows()` 自动标记 merged PR → done，
再列出 active flows。不需要新命令，不重复逻辑。

---

## 保留 vs 删除

### 保留（主干）

| 组件 | 原因 |
|------|------|
| `ensure_flow_for_current_branch()` | 被动注册，`plan/run/review` 都依赖 |
| `FlowService.create_flow()` | orchestra 调用（无 branch 操作） |
| `FlowService.get_current_branch()` | 所有命令依赖 |
| `FlowService.ensure_flow_for_branch()` | 被动注册核心 |
| `FlowService.block_flow()` | 还有用 |
| `flow add` 命令 | 显式注册当前 branch |
| `flow bind` 命令 | 绑定 issue |
| `flow show/status/list` 命令 | 状态查看 |
| `flow blocked` 命令 | 标记阻塞 |
| `handoff` 全部 | agent 链路记录，不变 |
| `orchestra/*` 全部 | 自动调度，不变 |
| `check_service` 全部 | check --fix --all 已完整实现清理逻辑 |
| `utils/branch_utils.find_parent_branch()` | 已实现，只需接入展示层 |
| `TaskService.link_issue()` | bind 的底层，保留 |

### 删除

| 文件/组件 | 行数 | 原因 |
|-----------|------|------|
| `services/flow_usecase.py` | 277 | 全部是 flow create 的 worktree governance |
| `services/flow_close_ops.py` | 373 | 全部是 flow done 的 branch/worktree 删除 |
| `services/flow_create_decision.py` | ~80 | 仅被 FlowUsecase 使用 |
| `services/base_resolution_usecase.py` | ~100 | 仅被 FlowUsecase 使用（find_parent_branch 在 utils 保留）|
| `services/flow_lifecycle.py` 部分 | ~50 | 删 close_flow/abort_flow，保留 block_flow |
| `FlowService.create_flow_with_branch()` | ~45 | git 的工作 |
| `FlowService.switch_flow()` | ~25 | 等于 `git checkout` |
| `commands/flow.py` `create`/`new` 函数 | ~80 | 删除 |
| `commands/flow_lifecycle.py` `done`/`aborted`/`switch` | ~120 | 删除 |
| `clients/github_project_*.py`（3 个文件） | ~750 | Project 是展示层，非主干 |
| **合计** | **~1900 行** | |

### 修改（净增约 20 行）

| 组件 | 改动 | 说明 |
|------|------|------|
| `commands/flow_status.py` `show()` | +5 行 | 展示 `find_parent_branch()` 结果 |
| `commands/flow_status.py` `status()` | +5 行 | 执行前调 `CheckService().verify_all_flows()` |
| `commands/command_options.py` | 改 1 行 | 错误提示改为 `git checkout -b` |
| `skills/vibe-new/SKILL.md` | 改 5 行 | 删 `flow create`，改为 `git checkout -b` |
| `skills/vibe-done/SKILL.md` | 改 10 行 | 删 `flow done`，改为 `check --fix --all` |
| `skills/vibe-instruction/SKILL.md` | 改 2 行 | 删 `flow create` 示例 |

---

## 实现步骤

### Step 1：验证被动注册路径（无代码改动）

确认当前 `ensure_flow_for_current_branch()` 不需要 `flow create`：

```bash
git checkout -b test/flow-passive-verify
uv run python src/vibe3/cli.py flow show    # 应自动注册并显示
uv run python src/vibe3/cli.py flow bind 1  # 应能绑定 issue
git checkout -
git branch -d test/flow-passive-verify
```

**验证通过后继续。**

---

### Step 2：flow show 展示 parent branch

`find_parent_branch()` 已在 `utils/branch_utils.py` 实现，只需接入展示层。

**改动位置**：`commands/flow_status.py` 的 `show()` 函数，在渲染 `render_flow_status()` 前追加：

```python
from vibe3.utils.branch_utils import find_parent_branch

parent = find_parent_branch(target_branch)
# 传入 render_flow_status() 或直接在输出中追加一行
```

同步更新 `ui/flow_ui.py` 的 `render_flow_status()` 接受 `parent_branch: str | None` 参数并展示。

**验证**：
```bash
git checkout -b test/parent-display
uv run python src/vibe3/cli.py flow show
# 预期：显示 parent: main（或来源 branch）
git checkout -
git branch -d test/parent-display
uv run pytest tests/vibe3/ -k "flow_show or flow_status"
uv run mypy src/vibe3
```

---

### Step 3：flow status 自动触发 check

`flow status` 执行前先调 `CheckService().verify_all_flows()`，自动标记 merged PR 为 done，
然后再列出 active flows。不新增命令，复用已有逻辑。

**改动位置**：`commands/flow_status.py` 的 `status()` 函数开头：

```python
from vibe3.services.check_service import CheckService

# Auto-mark merged flows before listing
try:
    CheckService().verify_all_flows()
except Exception:
    pass  # check failure should not block status display
```

**验证**：
```bash
uv run python src/vibe3/cli.py flow status
# 预期：已 merged 的 PR 对应 flow 不再出现在 active 列表
uv run pytest tests/vibe3/ -k "flow_status or check"
```

---

### Step 4：内联 `bind` 命令的 FlowUsecase 依赖

`flow bind` 用了 `FlowUsecase.validate_issue_refs()`（15 行静态方法）和
`FlowUsecase.bind_issue()`（3 行）。直接内联，移除 FlowUsecase 依赖：

```python
# commands/flow.py bind() 改为：
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
- 删除 `create()` 函数（~80 行）
- 删除 `new()` 函数（~15 行，已 deprecated）
- 删除 `FlowUsecase` import

`commands/command_options.py`：
```python
# 改前：typer.echo("  vibe3 flow create <name>", err=True)
# 改后：typer.echo("  git checkout -b <branch-name>", err=True)
```

**验证**：
```bash
uv run python src/vibe3/cli.py flow --help  # 不出现 create
uv run pytest tests/vibe3/ -x
uv run mypy src/vibe3
```

---

### Step 6：删除 `flow done` / `flow aborted` / `flow switch` 命令

`commands/flow_lifecycle.py`：删除 `done()`、`aborted()`、`switch()`，保留 `blocked()`。

从 `commands/flow.py` 注册行中同步移除这三个。

**验证**：
```bash
uv run python src/vibe3/cli.py flow --help  # 不出现 done/aborted/switch
uv run pytest tests/vibe3/ -x
```

---

### Step 7：删除 FlowService 的 git 操作方法

`services/flow_service.py`：删除 `create_flow_with_branch()`、`switch_flow()`、`close_flow()` 委托。

`services/flow_lifecycle.py`：删除 `close_flow()`、`abort_flow()`、`_abort_flow_impl()`，保留 `block_flow()`。

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

注意：`base_resolution_usecase.py` 引用了 `find_parent_branch`，但该函数在 `utils/branch_utils.py` 保留，删除文件不影响该函数。

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
  - 替换为：`gh pr merge <N>` + `vibe3 check --fix --all`（复用已有能力）
- `skills/vibe-new/SKILL.md`：
  - 删除"场景A：`vibe3 flow create <name> --task <issue> --base main`"
  - 替换为：`git checkout -b task/issue-<N>` + `vibe3 flow add`（注册已有 branch）
- `skills/vibe-instruction/SKILL.md`：删除 `flow create` 示例行

---

## 风险与回滚

| 风险 | 可能性 | 缓解 |
|------|--------|------|
| orchestra 依赖 `close_flow` | 低 | `FlowOrchestrator` 只用 `create_flow()`，已确认 |
| 测试 mock 了 `FlowUsecase` | 中 | Step 8 前先跑 `pytest -x`，零失败再删 |
| `task_service` 依赖 Project client | 中 | Step 9 前 inspect symbols 确认 |
| `verify_all_flows()` 网络调用影响 `flow status` 速度 | 低 | 用 `try/except` 包裹，失败静默跳过 |
| `find_parent_branch()` 在大仓库慢 | 低 | 仅在 `flow show` 单 branch 场景调用，不在 `flow status` 批量调用 |

**回滚**：每 Step 独立 commit，失败 `git revert <sha>`。

---

## 验收标准

```bash
# 1. 被动注册
git checkout -b test/verify-simplified
uv run python src/vibe3/cli.py flow show
# 预期：自动注册，显示 parent: main，显示 branch/pr/events

# 2. 绑定 issue
uv run python src/vibe3/cli.py flow bind 42
uv run python src/vibe3/cli.py flow show
# 预期：task: #42

# 3. flow status 自动清理
uv run python src/vibe3/cli.py flow status
# 预期：merged PR 对应 flow 不出现在 active 列表

# 4. 主干命令正常
uv run python src/vibe3/cli.py plan --help
uv run python src/vibe3/cli.py run --help
uv run python src/vibe3/cli.py review --help

# 5. flow create/done 不再存在
uv run python src/vibe3/cli.py flow --help
# 预期：无 create / done / switch / aborted

# 6. 全量测试
uv run pytest tests/vibe3/ -x
uv run mypy src/vibe3
uv run ruff check src/vibe3

# 清理
git checkout -
git branch -d test/verify-simplified
```
