# Remove Takeover / Keep Live Session Guards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删除 `takeover` 命令语义、参数透传、事件与测试残留，同时保留 `runtime_session` / truly live session 的派发去重、清理保护与容量控制。

**Architecture:** 本次只做“第一步减法”，不重写 orchestration 主链。`owner session` 暂时不整体删除，但 `takeover` 这条低频高复杂度分支要直接拿掉；系统以后只保留“是否存在 truly live session”的硬保护，不再保留“显式接管 owner”的命令能力。

**Tech Stack:** Python, Typer CLI, pytest, ripgrep, uv

---

## Scope Guard

- 保留：
  - `runtime_session` 表与 `SessionRegistryService`
  - `ExecutionCoordinator` 的 duplicate dispatch 检查
  - `FlowCleanupService` 的 live-session 防误删检查
  - `CapacityService` 的 live-session 计数
- 删除：
  - `vibe3 task resume --takeover`
  - `allow_takeover`
  - `takeover_reason`
  - `takeover_worktree()`
  - `worktree_takeover` 事件
  - 所有直接引用 `vibe3 task resume --takeover` 的用户可见文案
- 本轮不做：
  - 全面删除 `owner session` 数据层概念
  - 将全部 ownership guard 改写为 live-session guard
  - 重构 `runtime_session` 表结构

## File Map

**Modify**
- `src/vibe3/commands/task.py`
  - 删除 `--takeover` CLI 参数、help、docstring/example 文案、参数透传。
- `src/vibe3/services/task_resume_usecase.py`
  - 删除 `allow_takeover` 参数与向下透传。
- `src/vibe3/services/task_resume_operations.py`
  - 删除 `allow_takeover` 参数与 `takeover_reason` 透传。
- `src/vibe3/services/worktree_ownership_guard.py`
  - 删除 `takeover_worktree()`、`allow_takeover`、`takeover_reason` 分支；`ensure_worktree_ownership()` 只保留“发现 mismatch 则报错”。
- `src/vibe3/services/check_ownership_service.py`
  - 删除引用 `task resume --takeover` 的提示文本，改成人工检查 / 等待活跃会话结束。
- `src/vibe3/services/flow_cleanup_service.py`
  - 删除引用 `task resume --takeover` 的提示文本，改成“活跃 session 存在，停止 cleanup”。

**Modify Tests**
- `tests/vibe3/services/test_worktree_ownership_guard.py`
  - 删除 takeover 相关测试，保留 mismatch / outside tmux / unowned worktree 行为。
- `tests/vibe3/services/test_task_resume_operations.py`
  - 删除对 `allow_takeover` / takeover 路径的断言与 patch 残留。

**Search / Audit**
- `src/vibe3/`
- `tests/vibe3/`
- `docs/`
  - 搜索残留字符串：`allow_takeover|--takeover|takeover_worktree|worktree_takeover|takeover_reason`

---

### Task 1: Remove CLI And Usecase Plumbing

**Files:**
- Modify: `src/vibe3/commands/task.py`
- Modify: `src/vibe3/services/task_resume_usecase.py`

- [ ] **Step 1: Write failing grep-based expectation**

Run:

```bash
rg -n "allow_takeover|--takeover" src/vibe3/commands/task.py src/vibe3/services/task_resume_usecase.py
```

Expected: matches in both files, proving the command surface and usecase plumbing still exist.

- [ ] **Step 2: Remove the `--takeover` CLI option and examples**

Edit `src/vibe3/commands/task.py`:

```python
# delete this option block entirely
takeover: Annotated[
    bool,
    typer.Option(
        "--takeover",
        help="Explicitly take over worktree ownership from another session",
    ),
] = False,
```

Also remove:

```python
allow_takeover=takeover,
```

And delete any `--takeover` mentions from the command docstring/examples.

- [ ] **Step 3: Remove `allow_takeover` from the usecase signature and forwarding**

Edit `src/vibe3/services/task_resume_usecase.py`:

```python
def resume_issues(
    self,
    issue_numbers: list[int] | None = None,
    reason: str = "",
    dry_run: bool = False,
    flows: list[FlowStatusResponse] | None = None,
    stale_flows: list[FlowStatusResponse] | None = None,
    repo: str | None = None,
    candidate_mode: str = "resumable",
    label_state: str | None = None,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
```

And delete:

```python
allow_takeover=allow_takeover,
```

- [ ] **Step 4: Run focused verification**

Run:

```bash
rg -n "allow_takeover|--takeover" src/vibe3/commands/task.py src/vibe3/services/task_resume_usecase.py
```

Expected: no output.

- [ ] **Step 5: Commit**

```bash
git add src/vibe3/commands/task.py src/vibe3/services/task_resume_usecase.py
git commit -m "refactor(task): remove takeover CLI plumbing"
```

---

### Task 2: Delete Takeover Logic From Ownership Guard

**Files:**
- Modify: `src/vibe3/services/worktree_ownership_guard.py`
- Test: `tests/vibe3/services/test_worktree_ownership_guard.py`

- [ ] **Step 1: Write the failing test expectation**

Run:

```bash
uv run pytest tests/vibe3/services/test_worktree_ownership_guard.py -q
```

Expected: PASS before edits, giving a safety baseline.

- [ ] **Step 2: Remove takeover API and simplify mismatch behavior**

Edit `src/vibe3/services/worktree_ownership_guard.py`:

```python
def ensure_worktree_ownership(
    store: SQLiteClient,
    worktree_path: str,
) -> None:
```

Delete all of the following:

```python
allow_takeover: bool = False
takeover_reason: str = ""

if allow_takeover:
    takeover_worktree(...)
    return

def takeover_worktree(...):
    ...
```

Keep this behavior:

```python
if current_session_id is None:
    return
if owner_session is None:
    return
if not owner_tmux_session:
    return
if current_session_id == owner_tmux_session:
    return
raise WorktreeOwnerMismatchError(...)
```

- [ ] **Step 3: Remove takeover-specific messaging from the error**

Update the error body so it no longer instructs users to run `vibe3 task resume --takeover`.

Keep it simple:

```python
raise WorktreeOwnerMismatchError(
    f"Worktree ownership mismatch detected:\n"
    f"  Worktree: {worktree_path}{branch_hint}\n"
    f"  Current session: {current_session_id}\n"
    f"  Owner session: {owner_tmux_session} ({owner_session_name})\n\n"
    "This worktree appears to be in use by another tmux session. "
    "Wait for that session to finish or inspect the runtime session registry "
    "before continuing."
)
```

- [ ] **Step 4: Rewrite tests to match the reduced contract**

In `tests/vibe3/services/test_worktree_ownership_guard.py`:

- Remove import of `takeover_worktree`
- Delete tests:

```python
def test_allows_takeover_when_requested(...)
def test_logs_event_and_updates_owner(...)
```

- Replace takeover string assertion with a simpler mismatch assertion:

```python
assert "vibe3 task resume --takeover" not in error_msg
assert "Wait for that session to finish" in error_msg
```

- [ ] **Step 5: Run focused verification**

Run:

```bash
uv run pytest tests/vibe3/services/test_worktree_ownership_guard.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/vibe3/services/worktree_ownership_guard.py tests/vibe3/services/test_worktree_ownership_guard.py
git commit -m "refactor(runtime): remove takeover from ownership guard"
```

---

### Task 3: Remove Takeover From Resume Operations And Residual User Messages

**Files:**
- Modify: `src/vibe3/services/task_resume_operations.py`
- Modify: `src/vibe3/services/check_ownership_service.py`
- Modify: `src/vibe3/services/flow_cleanup_service.py`
- Test: `tests/vibe3/services/test_task_resume_operations.py`

- [ ] **Step 1: Write failing grep-based expectation**

Run:

```bash
rg -n "allow_takeover|takeover_reason|task resume --takeover|worktree_takeover" \
  src/vibe3/services/task_resume_operations.py \
  src/vibe3/services/check_ownership_service.py \
  src/vibe3/services/flow_cleanup_service.py \
  tests/vibe3/services/test_task_resume_operations.py
```

Expected: matches in all four files.

- [ ] **Step 2: Remove takeover parameters from resume operations**

Edit `src/vibe3/services/task_resume_operations.py`:

```python
def reset_issue_to_ready(
    self,
    *,
    issue_number: int,
    resume_kind: str,
    flow: FlowStatusResponse | None,
    repo: str | None,
    reason: str,
    worktree_path: str | None = None,
    label_state: str | None = None,
    progress_callback: ProgressCallback | None = None,
) -> None:
```

And change the ownership guard call to:

```python
ensure_worktree_ownership(
    self.flow_service.store,
    str(wt_path),
)
```

- [ ] **Step 3: Remove takeover wording from service messages**

Edit `src/vibe3/services/check_ownership_service.py` and `src/vibe3/services/flow_cleanup_service.py` to replace takeover instructions with plain stop/inspect guidance.

Use wording like:

```python
"Inspect the live runtime session and wait for it to finish before retrying."
```

and:

```python
"Active runtime sessions are still present; stop cleanup and investigate before retrying."
```

- [ ] **Step 4: Update resume operation tests**

In `tests/vibe3/services/test_task_resume_operations.py`:

- Remove patches or assertions that assume takeover behavior.
- Keep only baseline ownership/no-tmux behavior, for example:

```python
with patch(
    "vibe3.services.worktree_ownership_guard.get_current_session_id"
) as mock_session:
    mock_session.return_value = None
```

No test in this file should mention `allow_takeover`, `takeover_reason`, or `worktree_takeover`.

- [ ] **Step 5: Run focused verification**

Run:

```bash
uv run pytest tests/vibe3/services/test_task_resume_operations.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add \
  src/vibe3/services/task_resume_operations.py \
  src/vibe3/services/check_ownership_service.py \
  src/vibe3/services/flow_cleanup_service.py \
  tests/vibe3/services/test_task_resume_operations.py
git commit -m "refactor(resume): remove takeover behavior and messaging"
```

---

### Task 4: Residual Sweep And Regression Check

**Files:**
- Modify: any remaining files found by grep

- [ ] **Step 1: Run residual search across source, tests, and docs**

Run:

```bash
rg -n "allow_takeover|--takeover|takeover_worktree|worktree_takeover|takeover_reason|task resume --takeover" \
  src/vibe3 tests/vibe3 docs
```

Expected: no output.

- [ ] **Step 2: Run targeted regression suite**

Run:

```bash
uv run pytest \
  tests/vibe3/services/test_worktree_ownership_guard.py \
  tests/vibe3/services/test_task_resume_operations.py \
  -q
```

Expected: PASS.

- [ ] **Step 3: Run command/help smoke test**

Run:

```bash
uv run python src/vibe3/cli.py task resume --help
```

Expected:

```text
no "--takeover" option appears in help output
```

- [ ] **Step 4: Final audit of touched runtime protections**

Run:

```bash
rg -n "get_truly_live_sessions_for_target|get_truly_live_sessions_for_branch|count_live_worker_sessions" \
  src/vibe3/execution src/vibe3/services src/vibe3/environment
```

Expected: live-session guard code still present in coordinator / cleanup / capacity paths.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore(runtime): remove remaining takeover references"
```

---

## Self-Review

- Spec coverage:
  - 删除 CLI takeover：Task 1
  - 删除 guard takeover 逻辑与事件：Task 2
  - 删除 resume 透传与提示文案：Task 3
  - 清扫残留与回归验证：Task 4
- Placeholder scan:
  - 已为每个任务给出具体文件、命令、预期结果。
- Type consistency:
  - 所有步骤最终目标都是彻底消除 `allow_takeover` / `takeover_reason` / `takeover_worktree()`。

## Success Criteria

- `vibe3 task resume --help` 中不再出现 `--takeover`
- 仓库中不再存在 `allow_takeover` / `takeover_reason` / `takeover_worktree` / `worktree_takeover`
- targeted pytest 通过
- duplicate dispatch / cleanup live-session guard / capacity 逻辑未受影响
