# Flow Single-Target Governance Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 flow 语义收敛为单 worktree 单目标的强约束模型，禁止单目录多目标并行，优先保证 human 与 agent 行为规范性。

**Architecture:** 以 worktree 作为物理隔离单元，以 flow 作为当前交付目标的唯一运行时包装。`active` flow 下禁止在当前 worktree 中继续 `create`，只有显式 `blocked` 后才允许从当前 branch 派生下游 flow；独立新 feature 必须通过新 worktree 开启。

**Tech Stack:** Python 3.10+, Typer CLI, SQLite runtime store, pytest, mypy

---

## 强约束规则

1. 一个 worktree 同时只允许一个当前交付目标。
2. 当前 flow 为 `active` 时，拒绝在当前 worktree 执行 `flow create`。
3. 当前 flow 为 `blocked` 时，允许 `flow create`，默认从当前 branch 切出新 branch。
4. 新 feature 不允许在当前 worktree 直接开启，必须引导 `wtnew`。
5. 新 worktree 启动后重新检测现场；若无活动 flow，则默认从 `origin/main` 创建新 branch。
6. `done` 只负责结束当前 flow，并将当前目录落到上游 branch 或安全 branch。
7. 不再通过 dependency issue 或 task 关系猜测分支去向。

## 非目标

1. 不支持单 worktree 内并行维护多个活跃目标。
2. 不支持自动猜测“也许用户想开的是独立 feature 还是下游修复流”。
3. 不保留旧的宽松 `--base current` 语义。

### Task 1: 固化 flow 状态机约束

**Files:**
- Modify: `src/vibe3/services/flow_service.py`
- Modify: `src/vibe3/services/flow_lifecycle.py`
- Test: `tests/vibe3/services/test_flow_lifecycle.py`

**Step 1: 写失败测试，覆盖 active/blocked/done 三类准入规则**

```python
def test_active_flow_rejects_create_in_same_worktree() -> None:
    ...


def test_blocked_flow_allows_create_from_current_branch() -> None:
    ...


def test_done_flow_can_start_new_target_from_safe_base() -> None:
    ...
```

**Step 2: 运行测试确认失败**

Run: `uv run pytest tests/vibe3/services/test_flow_lifecycle.py -q`
Expected: FAIL，提示 create 准入逻辑尚未实现

**Step 3: 在 service 层增加显式准入判定**

```python
def can_create_from_current_worktree(...) -> CreateDecision:
    ...
```

要求：
- `active` -> reject
- `blocked` -> allow from current branch
- `done/aborted/no-flow` -> require fresh worktree check result to choose safe base

**Step 4: 运行测试确认通过**

Run: `uv run pytest tests/vibe3/services/test_flow_lifecycle.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/vibe3/services/test_flow_lifecycle.py src/vibe3/services/flow_service.py src/vibe3/services/flow_lifecycle.py
git commit -m "feat: enforce single-target flow state rules"
```

### Task 2: 收紧 flow create 命令语义

**Files:**
- Modify: `src/vibe3/commands/flow.py`
- Test: `tests/vibe3/commands/test_flow_commands.py`

**Step 1: 写失败测试，覆盖 CLI 拒绝与引导文案**

```python
def test_flow_create_rejects_when_current_flow_is_active() -> None:
    ...


def test_flow_create_guides_wtnew_for_new_feature() -> None:
    ...


def test_flow_create_defaults_to_current_branch_when_blocked() -> None:
    ...
```

**Step 2: 运行测试确认失败**

Run: `uv run pytest tests/vibe3/commands/test_flow_commands.py -q`
Expected: FAIL，CLI 仍接受宽松 create

**Step 3: 实现 CLI 规则**

```python
if current_flow_is_active:
    raise typer.Exit(1)

if current_flow_is_blocked:
    start_ref = current_branch
else:
    start_ref = "origin/main"
```

要求：
- `active` 时拒绝并提示 `wtnew`
- `blocked` 时自动从当前 branch 切
- 不再鼓励同 worktree 用 `--base current` 开新独立目标

**Step 4: 运行测试确认通过**

Run: `uv run pytest tests/vibe3/commands/test_flow_commands.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/vibe3/commands/test_flow_commands.py src/vibe3/commands/flow.py
git commit -m "feat: tighten flow create command semantics"
```

### Task 3: 定义 done 的安全回落行为

**Files:**
- Modify: `src/vibe3/services/flow_lifecycle.py`
- Test: `tests/vibe3/services/test_flow_lifecycle.py`

**Step 1: 写失败测试，覆盖上游/安全分支回落**

```python
def test_done_returns_to_parent_branch_when_available() -> None:
    ...


def test_done_falls_back_to_safe_branch_when_parent_unavailable() -> None:
    ...
```

**Step 2: 运行测试确认失败**

Run: `uv run pytest tests/vibe3/services/test_flow_lifecycle.py -q`
Expected: FAIL，当前实现仍包含推断逻辑或 main-only fallback

**Step 3: 用显式规则替代猜测逻辑**

```python
def resolve_close_target(...) -> CloseTargetDecision:
    ...
```

要求：
- 不依赖 dependency issue/task 猜测
- 优先回上游 branch
- 上游不可切时回安全 branch

**Step 4: 运行测试确认通过**

Run: `uv run pytest tests/vibe3/services/test_flow_lifecycle.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/vibe3/services/test_flow_lifecycle.py src/vibe3/services/flow_lifecycle.py
git commit -m "fix: use explicit fallback rules for flow done"
```

### Task 4: 文档化强约束并统一提示语

**Files:**
- Modify: `README.md`
- Modify: `docs/DEVELOPMENT.md`
- Modify: `docs/standards/v3/git-workflow-standard.md`

**Step 1: 写失败测试或快照检查（如已有 CLI 文案测试）**

```python
def test_flow_help_mentions_single_target_constraint() -> None:
    ...
```

**Step 2: 更新文档**

要求：
- 明确写出“单 worktree 单目标”
- 明确写出 `active` 不允许 `create`
- 明确写出 `blocked -> create` 为唯一派生入口
- 明确写出“新 feature 请 `wtnew`”

**Step 3: 运行文档相关测试或最小验证**

Run: `uv run pytest tests/vibe3/commands/test_flow_commands.py -q`
Expected: PASS

**Step 4: Commit**

```bash
git add README.md docs/DEVELOPMENT.md docs/standards/v3/git-workflow-standard.md
git commit -m "docs: codify single-target flow governance"
```

### Task 5: 全量验证

**Files:**
- Test: `tests/vibe3/services/test_flow_lifecycle.py`
- Test: `tests/vibe3/commands/test_flow_commands.py`

**Step 1: 跑聚焦测试**

Run: `uv run pytest tests/vibe3/services/test_flow_lifecycle.py tests/vibe3/commands/test_flow_commands.py -q`
Expected: PASS

**Step 2: 跑类型检查**

Run: `uv run mypy src/vibe3/services src/vibe3/commands`
Expected: Success: no issues found

**Step 3: Commit**

```bash
git add -A
git commit -m "test: validate single-target flow governance"
```

## 实施完成判定

1. human 在 active flow 中无法继续在同一 worktree 偷开新目标。
2. agent 在 active flow 中无法继续在同一 worktree 偷开新目标。
3. blocked 后 create 的默认行为稳定且唯一。
4. 新 feature 的推荐路径统一为 `wtnew`。
5. done 的回落行为不再依赖猜测。

## 执行建议

优先级建议：
1. Task 1
2. Task 2
3. Task 3
4. Task 4
5. Task 5

本方案故意牺牲灵活性，以换取可预测性、可审计性和跨 human/agent 的一致行为。