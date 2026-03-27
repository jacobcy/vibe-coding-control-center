# State Sync And Label Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 以“先确认事实、幂等确认、最小推进”为原则，补齐 `pr/flow/task` 状态同步与 `state/*`/`vibe-task` 标签联动。

**Architecture:** 复用现有 `PRService`、`FlowService`、`LabelService`、`TaskLabelService`，只在现有命令链路补“事实确认分支”和“缺失联动点”，不新增新的状态模型。保持真源边界：GitHub/Git 为事实真源，SQLite 为缓存确认层。

**Tech Stack:** Python 3.12, Typer CLI, pytest, gh CLI.

---

### Task 1: `pr ready` 与 `state/merge-ready` 幂等联动

**Files:**
- Modify: `src/vibe3/commands/pr_lifecycle.py`
- Modify: `src/vibe3/services/pr_ready_usecase.py`
- Modify: `src/vibe3/services/label_integration.py` (复用 `transition_issue_state`)
- Test: `tests/vibe3/services/test_pr_ready_usecase.py`
- Test: `tests/vibe3/commands/test_pr_ready.py`

**Step 1: 写失败测试（已 ready 时不重复门禁）**

```python
def test_mark_ready_already_ready_skips_gates_and_confirms_state():
    ...
```

**Step 2: 运行测试确认失败**

Run: `uv run pytest tests/vibe3/services/test_pr_ready_usecase.py -q`  
Expected: FAIL（当前会先跑 gates）

**Step 3: 最小实现**

- 在 usecase 先读取 PR 事实：已 ready 则直接确认返回。
- 成功 ready 后将对应 issue 迁移到 `state/merge-ready`（幂等）。

**Step 4: 运行测试确认通过**

Run: `uv run pytest tests/vibe3/services/test_pr_ready_usecase.py tests/vibe3/commands/test_pr_ready.py -q`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/vibe3/commands/pr_lifecycle.py src/vibe3/services/pr_ready_usecase.py src/vibe3/services/label_integration.py tests/vibe3/services/test_pr_ready_usecase.py tests/vibe3/commands/test_pr_ready.py
git commit -m "feat(pr): make ready idempotent and sync merge-ready label"
```

### Task 2: `flow blocked` 与 `flow done` 的 `state/*` 联动

**Files:**
- Modify: `src/vibe3/commands/flow_lifecycle.py`
- Modify: `src/vibe3/services/flow_lifecycle.py`
- Modify: `src/vibe3/services/flow_pr_guard.py`
- Modify: `src/vibe3/services/pr_service.py`
- Test: `tests/vibe3/services/test_flow_lifecycle.py`
- Test: `tests/vibe3/commands/test_flow_done.py`

**Step 1: 写失败测试（done 可 merge 时先 merge）**

```python
def test_flow_done_merges_when_pr_is_mergeable_then_closes_flow():
    ...
```

**Step 2: 运行测试确认失败**

Run: `uv run pytest tests/vibe3/services/test_flow_lifecycle.py tests/vibe3/commands/test_flow_done.py -q`  
Expected: FAIL（当前未 merge 直接阻断）

**Step 3: 最小实现**

- `flow done` 先确认 PR 事实：
  - 已 merge：直接 closeout。
  - 未 merge但可 merge：先复用 `PRService.merge_pr()` 再 closeout。
- `flow blocked` 成功后迁移 `state/blocked`。
- `flow done` 完成后迁移 `state/done`（幂等）。

**Step 4: 运行测试确认通过**

Run: `uv run pytest tests/vibe3/services/test_flow_lifecycle.py tests/vibe3/commands/test_flow_done.py -q`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/vibe3/commands/flow_lifecycle.py src/vibe3/services/flow_lifecycle.py src/vibe3/services/flow_pr_guard.py src/vibe3/services/pr_service.py tests/vibe3/services/test_flow_lifecycle.py tests/vibe3/commands/test_flow_done.py
git commit -m "feat(flow): sync blocked/done labels and merge on done when possible"
```

### Task 3: 多 task closeout 与 `vibe-task` 镜像补偿

**Files:**
- Modify: `src/vibe3/services/flow_lifecycle.py`
- Modify: `src/vibe3/services/task_label_service.py`
- Modify: `src/vibe3/services/task_service.py`
- Modify: `src/vibe3/services/check_service.py`
- Test: `tests/vibe3/services/test_task_label_service.py`
- Test: `tests/vibe3/services/test_flow_lifecycle.py`
- Test: `tests/vibe3/services/test_check_service.py`

**Step 1: 写失败测试（done 关闭全部 `role=task`）**

```python
def test_flow_done_closes_all_task_role_issues():
    ...
```

**Step 2: 运行测试确认失败**

Run: `uv run pytest tests/vibe3/services/test_flow_lifecycle.py tests/vibe3/services/test_check_service.py -q`  
Expected: FAIL（当前不关闭 task issue，check 仍把多 task 当异常）

**Step 3: 最小实现**

- `flow done` 读取 `flow_issue_links` 中全部 `role=task`，逐个关闭对应 issue。
- `TaskLabelService` 增加幂等移除 `vibe-task` 方法（仅镜像层）。
- 调整 `check_service`：多 `task` 改为合法场景，不再报错。

**Step 4: 运行测试确认通过**

Run: `uv run pytest tests/vibe3/services/test_task_label_service.py tests/vibe3/services/test_flow_lifecycle.py tests/vibe3/services/test_check_service.py -q`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/vibe3/services/flow_lifecycle.py src/vibe3/services/task_label_service.py src/vibe3/services/task_service.py src/vibe3/services/check_service.py tests/vibe3/services/test_task_label_service.py tests/vibe3/services/test_flow_lifecycle.py tests/vibe3/services/test_check_service.py
git commit -m "feat(task): close all task issues on flow done and align vibe-task mirror"
```
