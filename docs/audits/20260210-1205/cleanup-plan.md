# Cleanup Plan
**Session ID:** 20260210-1205

## Objective
To eliminate technical debt identified in the audit, focusing on verifying the "Single Source of Truth" for installation logic and populating standardization files.

## Action Items

### 1. Consolidate Installation Scripts (High Priority)
- **Target**: `scripts/install.sh`
- **Action**:
    -   Modify `scripts/install.sh` to remove inline installation logic for Claude and OpenCode.
    -   Update it to call `zsh install/install-claude.sh` and `zsh install/install-opencode.sh` respectively.
    -   Ensure `install/install-claude.sh` handles idempotent checks (it already does per audit).

### 2. Populate Context Files (Medium Priority)
- **Target**: `MEMORY.md`, `TASK.md`, `WORKFLOW.md`
- **Action**: Add standard templates to these files to make them immediately useful for agents.

### 3. Verify & Report
- **Action**: Run `scripts/test-all.sh` after changes.
- **Action**: Generate `execution-report.md`.
