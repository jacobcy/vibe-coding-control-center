# Base Resolution Unification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 提供统一的 base 解析能力，并先让 `vibe3 pr create` 与 `vibe3 review base` 复用它。

**Architecture:** 在 `src/vibe3/services/` 新增一个 command-facing 的 base 解析用例层，负责显式 base、自动推断、错误翻译与最小提示信息；命令层只保留 CLI 参数、交互和 UI 输出。`pr_create` 继续保留 Prompt/AI 交互，`review base` 继续保留 review UI，但两者不再各自实现 base 推断逻辑。

**Tech Stack:** Python, Typer, pytest, uv

---

### Task 1: Add Failing Tests For Shared Base Resolution

**Files:**
- Create: `tests/vibe3/services/test_base_resolution_usecase.py`
- Modify: `tests/vibe3/commands/test_review_base.py`
- Test: `tests/vibe3/services/test_base_resolution_usecase.py`

**Step 1: Write the failing test**

```python
def test_resolve_explicit_base_returns_requested_branch():
    ...
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/vibe3/services/test_base_resolution_usecase.py -q`
Expected: FAIL because the new usecase module does not exist yet

**Step 3: Write minimal implementation**

```python
class BaseResolutionUsecase:
    ...
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/vibe3/services/test_base_resolution_usecase.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/vibe3/services/test_base_resolution_usecase.py src/vibe3/services/base_resolution_usecase.py
git commit -m "test: add base resolution usecase coverage"
```

### Task 2: Route Review Base Through Shared Resolution

**Files:**
- Modify: `src/vibe3/commands/review.py`
- Modify: `tests/vibe3/commands/test_review_base.py`
- Test: `tests/vibe3/commands/test_review_base.py`

**Step 1: Write the failing test**

```python
def test_review_base_uses_shared_resolution_when_base_omitted():
    ...
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/vibe3/commands/test_review_base.py -q`
Expected: FAIL because `review base` still resolves parent branch inline

**Step 3: Write minimal implementation**

```python
resolved = usecase.resolve_base(...)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/vibe3/commands/test_review_base.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/vibe3/commands/review.py tests/vibe3/commands/test_review_base.py
git commit -m "refactor: route review base through shared resolver"
```

### Task 3: Route PR Create Through Shared Resolution

**Files:**
- Modify: `src/vibe3/commands/pr_create.py`
- Modify: `tests/vibe3/commands/test_pr_create_ai.py`
- Test: `tests/vibe3/commands/test_pr_create_ai.py`

**Step 1: Write the failing test**

```python
def test_pr_create_uses_resolved_base_for_ai_context_and_pr_request():
    ...
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/vibe3/commands/test_pr_create_ai.py -q`
Expected: FAIL because `pr create` still uses raw `base` directly

**Step 3: Write minimal implementation**

```python
resolved_base = usecase.resolve_base(...)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/vibe3/commands/test_pr_create_ai.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/vibe3/commands/pr_create.py tests/vibe3/commands/test_pr_create_ai.py
git commit -m "refactor: share base resolution in pr create"
```

### Task 4: Verify Targeted Commands Stay Green

**Files:**
- Test: `tests/vibe3/services/test_base_resolution_usecase.py`
- Test: `tests/vibe3/commands/test_review_base.py`
- Test: `tests/vibe3/commands/test_pr_create_ai.py`

**Step 1: Run focused tests**

Run: `uv run pytest tests/vibe3/services/test_base_resolution_usecase.py tests/vibe3/commands/test_review_base.py tests/vibe3/commands/test_pr_create_ai.py -q`
Expected: PASS

**Step 2: Run lint on touched files**

Run: `uv run ruff check src/vibe3/commands/pr_create.py src/vibe3/commands/review.py src/vibe3/services/base_resolution_usecase.py tests/vibe3/services/test_base_resolution_usecase.py tests/vibe3/commands/test_review_base.py tests/vibe3/commands/test_pr_create_ai.py`
Expected: PASS

**Step 3: Commit**

```bash
git add docs/plans/2026-03-27-base-resolution-unification.md
git commit -m "docs: add base resolution unification plan"
```
