# Validation Boundary for flow_issue_links

## Overview

This document defines the intended validation boundary for `flow_issue_links` table writes and reads. It establishes the service layer as the sole validation guard for production writes, while preserving repository layer flexibility for test fixtures and corruption simulations.

## Write Boundary

**Rule**: All production `flow_issue_links` writes MUST pass through `TaskService.link_issue()`.

`TaskService.link_issue()` is the sole write guard. It validates that the target branch is not a protected base branch (e.g., `main`, `master`, `develop`) before allowing the write.

### Production Call Sites (All Pass Through Write Guard)

The following production callers correctly route through `TaskService.link_issue()`:

1. **Orchestrator._link_issue()** (`orchestrator.py:193,195`)
   - Roles: "task", "dependency", "related"

2. **FlowManager.upgrade_placeholder()** (`flow_manager.py:129`)
   - Role: "dependency"

3. **BlockMixin._link_issues()** (`block_mixin.py:76`)
   - Role: "dependency"

4. **CheckRemote.init_from_branches()** (`remote.py:159`)
   - Role: "task"

5. **CheckPRService._transfer_dependencies()** (`pr_service.py:186`)
   - Role: "dependency"
   - **Note**: This caller was previously bypassing the service guard by calling `store.add_issue_link()` directly. It has been updated to route through `TaskService.link_issue()`.

### Protected Branch Check

The guard in `TaskService.link_issue()` (lines 144-148) checks:
```python
base_branch = self._get_orchestra_config().scene_base_ref.replace("origin/", "")
if branch == base_branch or branch in protected_branches:
    raise InvalidBranchLinkError(...)
```

This check:
- Strips remote prefixes (e.g., `origin/`, `upstream/`) before comparison
- Compares against configured base branch and protected branches
- Raises `InvalidBranchLinkError` with `E_INVALID_BRANCH_LINK` classification

## Read Boundary

**Rule**: `IssueFlowService.find_active_flow()` and `resolve_best_flow()` detect corrupted base branch links on read.

The read guard ensures that even if historical corruption exists (e.g., from bugs in older versions), it will be detected when the data is read:

- `find_active_flow()` validates issue links before returning
- `resolve_best_flow()` performs similar validation
- Both raise `InvalidBranchLinkError` when detecting corrupted links

This read guard complements the write guard by catching historical corruption that predates the write guard.

## Repository Layer Contract

**Rule**: `SQLiteFlowStateRepo.add_issue_link()` is a persistence method with NO business validation.

The repository layer (`SQLiteFlowStateRepo.add_issue_link()` at `sqlite_flow_state_repo.py:132`) performs a pure `INSERT OR REPLACE` with zero validation. This is intentional:

1. **Preserves test flexibility**: 65+ test call sites use `add_issue_link()` directly for fixtures and corruption simulations.
2. **Enables corruption simulation**: Tests can insert "corrupt" data (e.g., `main` linked to issue 999) to verify that read guards detect it.
3. **Follows ADR-0002**: Repository is a concrete implementation that should be a dumb persistence layer. Validation belongs in the service layer.

## Test Exception

**Rule**: Test fixtures and corruption simulations may call `add_issue_link()` directly.

Tests are explicitly allowed to bypass the service guard to:
- Create test fixtures with arbitrary issue links
- Simulate corruption scenarios for read guard testing
- Test edge cases that shouldn't occur in production

This exception is documented and acceptable because:
- Tests run in isolated environments
- Corruption scenarios are intentionally created to verify defensive checks
- Production code is prevented from bypassing the guard

## Validation Strategy Summary

| Layer | Responsibility | Implementation |
|-------|---------------|----------------|
| **Service (Write)** | Guard all production writes | `TaskService.link_issue()` validates before write |
| **Service (Read)** | Detect historical corruption | `IssueFlowService.find_active_flow()` validates on read |
| **Repository** | Pure persistence | No validation; trust service layer |

This layered approach provides:
- **Defense in depth**: Write guard prevents new corruption; read guard catches old corruption
- **Test flexibility**: Repository layer remains accessible for test scenarios
- **Clear responsibility**: Service layer owns validation; repository layer owns persistence

## Related

- Merged delivery PR: #2024 (original service-layer guard implementation)
- Superseded exploratory PR: #2017 (attempted repo-layer validation)
- Original bug: #2010 (base branch link corruption)
- Historical integrity check/repair: #2035
- Read guard config consistency: #2030
