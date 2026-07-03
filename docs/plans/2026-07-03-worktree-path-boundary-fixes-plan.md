# Worktree Path Boundary Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the remaining repository-management-root versus checked-out-worktree-root confusion for both bare and non-bare repository layouts.

**Architecture:** Git worktree registration is the authority for executable checkout paths; symbolic `HEAD` on a management root is never sufficient. Shared SQLite state is rooted from Git's common directory, while initialization scripts are rooted from the newly created checkout.

**Tech Stack:** Python 3.12, pytest, Git CLI, Zsh/Bats, Ruff, mypy

## Global Constraints

- Support `bare_repo/.worktrees/<name>` and `main/.worktrees/<name>`.
- Use `repo_path` only for repository management and Git common-dir discovery.
- Use a registered checkout path for source access and execution cwd.
- Keep worktree initialization non-blocking.
- Use `uv run` for Python commands and targeted local tests only.
- Follow the repository's two-step commit discipline; never use `--no-verify`.

---

### Task 1: Make registered worktrees authoritative for execution cwd

**Files:**
- Create: `tests/vibe3/environment/test_worktree_path_boundaries.py`
- Modify: `src/vibe3/environment/worktree_lifecycle.py:359-439`
- Modify: `src/vibe3/environment/worktree.py:232-351`
- Modify: `src/vibe3/environment/worktree_support.py:294-308`
- Modify: `tests/vibe3/services/test_worktree_path_recording.py`

**Interfaces:**
- Consumes: `find_worktree_for_branch(repo_path: Path, branch: str) -> Path | None`
- Produces: `find_or_create_worktree_for_branch(...)` without `check_current_branch`; `resolve_bootstrap_worktree_context(use_worktree=False)` returns a registered checkout or raises `SystemError`

- [ ] **Step 1: Write real-topology failing tests**

Create a temporary source repository and a true bare clone. Register
`bare_repo/.worktrees/main`, then assert manager resolution returns that path,
not `bare_repo`. Add two bootstrap tests: `use_worktree=False` reuses a
registered branch checkout and raises `SystemError` when no checkout exists.

```python
import subprocess
from pathlib import Path

import pytest

from vibe3.environment.worktree import WorktreeManager
from vibe3.exceptions import SystemError
from vibe3.models.orchestra_config import OrchestraConfig


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def bare_repo_with_main_worktree(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "source"
    source.mkdir()
    _git(source, "init", "-b", "main")
    _git(source, "config", "user.name", "Test")
    _git(source, "config", "user.email", "test@example.com")
    (source / "README.md").write_text("test\n")
    _git(source, "add", "README.md")
    _git(source, "commit", "-m", "init")

    bare_repo = tmp_path / "repo.git"
    subprocess.run(
        ["git", "clone", "--bare", str(source), str(bare_repo)],
        check=True,
        capture_output=True,
        text=True,
    )
    main_worktree = bare_repo / ".worktrees" / "main"
    main_worktree.parent.mkdir()
    _git(bare_repo, "worktree", "add", str(main_worktree), "main")
    return bare_repo, main_worktree


def test_bare_repo_head_is_not_returned_as_checkout(bare_repo_with_main_worktree):
    repo_path, main_worktree = bare_repo_with_main_worktree
    manager = WorktreeManager(OrchestraConfig(), repo_path)

    cwd, missing = manager.resolve_manager_cwd(1, "main")

    assert missing is False
    assert cwd == main_worktree


def test_no_worktree_mode_reuses_registered_checkout(bare_repo_with_main_worktree):
    repo_path, main_worktree = bare_repo_with_main_worktree
    manager = WorktreeManager(OrchestraConfig(), repo_path)

    context = manager.resolve_bootstrap_worktree_context(
        branch="main", issue_number=1, use_worktree=False
    )

    assert context.path == main_worktree


def test_no_worktree_mode_rejects_management_root_without_checkout(
    bare_repo_with_main_worktree,
):
    bare_repo, _ = bare_repo_with_main_worktree
    manager = WorktreeManager(OrchestraConfig(), bare_repo)

    with pytest.raises(SystemError, match="No registered worktree"):
        manager.resolve_bootstrap_worktree_context(
            branch="missing", issue_number=1, use_worktree=False
        )
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
uv run pytest tests/vibe3/environment/test_worktree_path_boundaries.py -q
```

Expected: the current implementation returns `bare_repo` for the first two
tests and does not raise for the third.

- [ ] **Step 3: Remove the symbolic-HEAD shortcut**

Delete `check_current_branch` from the wrapper and lifecycle signatures,
docstrings, and call sites. Delete the `is_current_branch()` helper. Keep the
resolution sequence as recorded path, registered worktree, then worktree
creation. Remove obsolete mocks from
`tests/vibe3/services/test_worktree_path_recording.py`.

For `use_worktree=False`, use the registered-worktree resolver:

```python
if not use_worktree:
    existing = find_worktree_for_branch(self.repo_path, branch)
    if existing is None:
        raise SystemError(
            f"No registered worktree for branch {branch}; "
            "repository management root is not an execution checkout"
        )
    return WorktreeContext(
        path=existing,
        is_temporary=False,
        branch=branch,
        issue_number=issue_number,
    )
```

- [ ] **Step 4: Run focused tests and verify GREEN**

Run:

```bash
uv run pytest tests/vibe3/environment/test_worktree_path_boundaries.py tests/vibe3/services/test_worktree_path_recording.py -q
uv run ruff check src/vibe3/environment tests/vibe3/environment/test_worktree_path_boundaries.py tests/vibe3/services/test_worktree_path_recording.py
uv run mypy src/vibe3/environment/worktree.py src/vibe3/environment/worktree_lifecycle.py src/vibe3/environment/worktree_support.py
```

Expected: all commands exit 0.

- [ ] **Step 5: Commit the task using the required two-step workflow**

Create a temporary commit so hooks can apply fixes, reset it with
`git reset HEAD^`, then create the formal commit:

```bash
git add src/vibe3/environment/worktree.py src/vibe3/environment/worktree_lifecycle.py src/vibe3/environment/worktree_support.py tests/vibe3/environment/test_worktree_path_boundaries.py tests/vibe3/services/test_worktree_path_recording.py
git commit -m "temp: validate worktree checkout resolution"
git reset HEAD^
git add src/vibe3/environment/worktree.py src/vibe3/environment/worktree_lifecycle.py src/vibe3/environment/worktree_support.py tests/vibe3/environment/test_worktree_path_boundaries.py tests/vibe3/services/test_worktree_path_recording.py
git commit -m "fix(worktree): require registered checkout paths"
```

### Task 2: Resolve SQLite state from Git common directory

**Files:**
- Modify: `tests/vibe3/clients/test_sqlite_client_fresh_db.py:128-148`
- Modify: `src/vibe3/clients/sqlite_base.py:137-151`

**Interfaces:**
- Consumes: `GitClient(cwd=repo_path).get_git_common_dir() -> str`
- Produces: `SQLiteClient.from_repo_path(repo_path)` with topology-independent shared DB placement

- [ ] **Step 1: Add bare and non-bare failing tests**

Use real Git repositories and assert both expected common-dir paths:

```python
def _init_non_bare_repo(path: Path) -> None:
    subprocess.run(
        ["git", "init", "-b", "main", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )


def test_non_bare_repo_uses_dot_git_common_dir(tmp_path: Path) -> None:
    non_bare_repo = tmp_path / "main"
    _init_non_bare_repo(non_bare_repo)

    store = SQLiteClient.from_repo_path(non_bare_repo)

    assert Path(store.db_path) == (
        non_bare_repo / ".git" / "vibe3" / "handoff.db"
    )


def test_bare_repo_uses_repo_as_common_dir(tmp_path: Path) -> None:
    non_bare_repo = tmp_path / "main"
    _init_non_bare_repo(non_bare_repo)
    bare_repo = tmp_path / "repo.git"
    subprocess.run(
        ["git", "clone", "--bare", str(non_bare_repo), str(bare_repo)],
        check=True,
        capture_output=True,
        text=True,
    )

    store = SQLiteClient.from_repo_path(bare_repo)

    assert Path(store.db_path) == bare_repo / "vibe3" / "handoff.db"
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
uv run pytest tests/vibe3/clients/test_sqlite_client_fresh_db.py::TestFromRepoPath -q
```

Expected: the bare test fails because the implementation appends `.git`.

- [ ] **Step 3: Implement common-dir resolution**

Replace `repo_path / ".git"` with instance-scoped Git discovery and create the
shared state directory before opening SQLite:

```python
git_common_dir = GitClient(cwd=repo_path).get_git_common_dir()
if not git_common_dir:
    raise GitError("rev-parse --git-common-dir", "returned empty path")
git_dir = Path(git_common_dir)
if not git_dir.is_absolute():
    raise GitError(
        "rev-parse --git-common-dir",
        f"returned non-absolute path: {git_dir}",
    )
git_dir.joinpath("vibe3").mkdir(parents=True, exist_ok=True)
return cls(db_path=str(get_vibe3_db_path(git_dir)))
```

- [ ] **Step 4: Run focused tests and verify GREEN**

Run:

```bash
uv run pytest tests/vibe3/clients/test_sqlite_client_fresh_db.py -q
uv run ruff check src/vibe3/clients/sqlite_base.py tests/vibe3/clients/test_sqlite_client_fresh_db.py
uv run mypy src/vibe3/clients/sqlite_base.py
```

Expected: all commands exit 0.

- [ ] **Step 5: Commit the task using the required two-step workflow**

```bash
git add src/vibe3/clients/sqlite_base.py tests/vibe3/clients/test_sqlite_client_fresh_db.py
git commit -m "temp: validate bare repository sqlite paths"
git reset HEAD^
git add src/vibe3/clients/sqlite_base.py tests/vibe3/clients/test_sqlite_client_fresh_db.py
git commit -m "fix(sqlite): resolve state from git common dir"
```

### Task 3: Run V2 initialization from the new checkout

**Files:**
- Modify: `tests/vibe2/contracts/test_worktree_alias.bats`
- Modify: `lib/alias/worktree.sh:45-60,191`

**Interfaces:**
- Produces: `_vibe_worktree_run_init(worktree_path)`; the helper reads and executes `<worktree_path>/scripts/init.sh`

- [ ] **Step 1: Add the failing V2 regression test**

Create a management root without `scripts/init.sh`, place the script only in
its worktree, and require a relative marker in the worktree cwd:

```bash
@test "worktree init resolves script from checkout root" {
  local repo_root worktree_path
  repo_root="$(mktemp -d)"
  worktree_path="$repo_root/.worktrees/topic"
  mkdir -p "$worktree_path/scripts"
  printf '#!/usr/bin/env bash\ntouch .init-ran\n' > "$worktree_path/scripts/init.sh"

  run_zsh_with_timeout "source \"$VIBE_ROOT/lib/utils.sh\"; source \"$VIBE_ROOT/lib/alias/worktree.sh\"; _vibe_worktree_run_init \"$worktree_path\""

  [ "$status" -eq 0 ]
  [ -f "$worktree_path/.init-ran" ]
  rm -rf "$repo_root"
}
```

- [ ] **Step 2: Run the Bats test and verify RED**

Run:

```bash
bats --filter "worktree init resolves" tests/vibe2/contracts/test_worktree_alias.bats
```

Expected: the helper does not create `.init-ran`.

- [ ] **Step 3: Change the helper boundary**

Remove the unused management-root argument, resolve the script from the
checkout, and update `wtnew()`:

```zsh
_vibe_worktree_run_init() {
  local worktree_path="$1"
  local init_script="$worktree_path/scripts/init.sh"

  [[ -f "$init_script" ]] || return 0

  echo "🔧 Running initialization script..."
  (
    cd "$worktree_path" &&
      bash "$init_script"
  ) || {
    echo "⚠️  Init script failed (non-fatal)"
    return 0
  }
}
```

Call it with `_vibe_worktree_run_init "$path"`.

- [ ] **Step 4: Run focused verification and verify GREEN**

Run:

```bash
zsh -n lib/alias/worktree.sh
bats tests/vibe2/contracts/test_worktree_alias.bats
```

Expected: syntax check exits 0 and all Bats tests pass.

- [ ] **Step 5: Commit the task using the required two-step workflow**

```bash
git add lib/alias/worktree.sh tests/vibe2/contracts/test_worktree_alias.bats
git commit -m "temp: validate worktree-local v2 init"
git reset HEAD^
git add lib/alias/worktree.sh tests/vibe2/contracts/test_worktree_alias.bats
git commit -m "fix(worktree): run v2 init from checkout root"
```

### Task 4: Final targeted regression

**Files:**
- Verify only; no planned source changes

**Interfaces:**
- Consumes all behavior produced by Tasks 1-3
- Produces fresh completion evidence

- [ ] **Step 1: Run the affected Python suites**

```bash
uv run pytest tests/vibe3/environment tests/vibe3/services/test_worktree_path_recording.py tests/vibe3/clients/test_sqlite_client_fresh_db.py -q
```

- [ ] **Step 2: Run static checks**

```bash
uv run ruff check src/vibe3/environment src/vibe3/clients/sqlite_base.py tests/vibe3/environment tests/vibe3/services/test_worktree_path_recording.py tests/vibe3/clients/test_sqlite_client_fresh_db.py
uv run mypy src/vibe3/environment/worktree.py src/vibe3/environment/worktree_lifecycle.py src/vibe3/environment/worktree_support.py src/vibe3/clients/sqlite_base.py
zsh -n lib/alias/worktree.sh
bats tests/vibe2/contracts/test_worktree_alias.bats
git diff --check HEAD~3...HEAD
```

- [ ] **Step 3: Confirm branch state and reviewed commits**

```bash
git status --short --branch
git log --oneline -6
```

Expected: the worktree is clean, the three formal fix commits are present, and
all targeted verification commands exit 0.
