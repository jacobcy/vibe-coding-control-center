# Fix Directive: Issue #1779 — MAJOR Issues Found in Review

**Date**: 2026-06-01
**From**: manager
**To**: executor
**Priority**: HIGH

---

## Context

Review found **2 MAJOR issues** that break core functionality. The implementation has a critical bug in `_get_git_root` that causes wrong path resolution when run from subdirectories in non-worktree cases.

---

## MAJOR Issues to Fix

### 1. Fix `_get_git_root` Path Resolution

**Problem**: `src/vibe3/services/project_check_service.py:101-106`

The current implementation uses `git rev-parse --git-common-dir` which returns:
- **Worktree**: absolute path → ✅ works
- **Non-worktree (repo root)**: `.git` (relative to cwd) → `Path(".git").parent = Path(".")` → ✅ works
- **Non-worktree (subdirectory)**: `../.git` (relative to cwd) → `Path("../.git").parent = Path("..")` → ❌ **WRONG**

**Impact**: When run from a subdirectory, `git_root` resolves to the wrong directory, causing all vibe3 config and Orchestra checks to inspect the wrong location.

**Fix Required**:
```python
def _get_git_root(self) -> Path | None:
    """Get the git repository root, correctly handling worktrees and subdirectories."""
    try:
        # Get the path to .git directory (or worktree git dir)
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True,
            text=True,
            check=True
        )
        git_dir = Path(result.stdout.strip())
        
        # If it's a relative path, resolve it from cwd
        if not git_dir.is_absolute():
            git_dir = (Path.cwd() / git_dir).resolve()
        
        # The git root is the parent of the .git directory
        git_root = git_dir.parent
        return git_root
    except subprocess.CalledProcessError:
        return None
```

**Why this works**:
- Resolves relative paths from cwd before taking parent
- Preserves absolute paths from worktrees
- Correctly handles all three cases

---

### 2. Add Direct Test Coverage for `_get_git_root`

**Problem**: All service tests mock `_get_git_root` via `patch.object()`. The actual path resolution logic is never exercised. Your claim of correct worktree handling is unverified.

**Fix Required**: Add integration test that exercises real `_get_git_root`:

```python
def test_get_git_root_from_subdirectory(tmp_path):
    """Test that _get_git_root works correctly from a subdirectory."""
    # Create a real git repo
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    subprocess.run(["git", "init"], cwd=repo_root, check=True)
    
    # Create a subdirectory
    subdir = repo_root / "subdir"
    subdir.mkdir()
    
    # Test from subdirectory
    service = ProjectCheckService()
    with patch.object(Path, 'cwd', return_value=subdir):
        git_root = service._get_git_root()
        assert git_root == repo_root, f"Expected {repo_root}, got {git_root}"
```

**Test scenarios to cover**:
1. Repo root (cwd = git root)
2. Subdirectory (cwd = git root / subdir)
3. Worktree (if possible to set up in test)

---

## MINOR Issues (Fix if Time Permits)

### 3. Orchestra "repo configuration valid" Check

**Problem**: Lines 486-498: hardcoded `status="pass"` while message says "skipped". Misleading.

**Fix**: Change to `status="skip"` or implement real validation.

---

### 4. `scene_base_ref` Check

**Problem**: Lines 501-535: checks `git rev-parse --verify main/master` instead of reading the actual configured `scene_base_ref`.

**Fix**: Read the actual `scene_base_ref` from config and check that branch.

---

## Verification Requirements

After fixing:

1. **All existing tests must still pass**: `uv run pytest tests/vibe3/services/test_project_check_service.py tests/vibe3/commands/test_project_check.py`

2. **New test must pass**: The new `_get_git_root` test must pass

3. **Manual verification**:
   ```bash
   # Test from repo root
   cd /path/to/repo
   vibe3 project-check
   
   # Test from subdirectory
   cd subdir
   vibe3 project-check
   
   # Both should give same results
   ```

4. **Type checks**: `uv run mypy src/vibe3/services/project_check_service.py`

5. **Lint checks**: `uv run ruff check src/vibe3/services/project_check_service.py`

---

## What NOT to Do

- ❌ Do NOT mock `_get_git_root` in the new test
- ❌ Do NOT skip the subdirectory case test
- ❌ Do NOT assume the current implementation is correct
- ❌ Do NOT add workarounds instead of fixing the root cause

---

## Success Criteria

- ✅ `_get_git_root` correctly resolves paths from any cwd
- ✅ Direct test coverage for `_get_git_root` with real git operations
- ✅ All existing tests still pass
- ✅ Manual verification from subdirectory works correctly

---

## Reference

- **Audit Report**: `docs/reports/issue-1779-audit-report.md`
- **Implementation**: `src/vibe3/services/project_check_service.py:101-106`
- **Tests**: `tests/vibe3/services/test_project_check_service.py`

---

## Questions?

If you're unsure about the fix approach, check how other tools handle this:
- `git rev-parse --show-toplevel` always returns absolute path to repo root
- But we need the git common dir for worktree support
- The key is resolving relative paths from cwd before use
