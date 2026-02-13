# PRD: Workflow Standardization Shell Support

## 1. Overview
Ensure consistency across all project workflows by providing dedicated shell scripts for "Provisioning", "Execution", and "Cleanup". This aligns with the existing TDD workflow and ensures that both human and AI agents follow standardized "prescribed actions".

## 2. Goals
- **Consistency**: All workflows should have a dedicated shell script to handle boilerplate setup.
- **Automation**: Common actions (directory creation, grouping files, cleaning up) should be standardized.
- **Unified CLI**: Users/Agents should interact via the `vibe` command (e.g., `vibe audit`, `vibe done`).

## 3. Scope
The following three workflows need support scripts and CLI integration.

### A. Audit & Cleanup Workflow
- **Script**: `scripts/audit-init.sh`
- **Function**: 
  - Generate a timestamped folder: `docs/audits/YYYYMMDD-HHMM`.
  - Create markdown templates: `doc-audit-report.md`, `code-audit-report.md`, `cleanup-plan.md`.
- **CLI Command**: `vibe audit new`

### B. Smart Commit Workflow
- **Script**: `scripts/commit-prep.sh`
- **Function**:
  - Analyze `git status`.
  - Suggest logical groupings (e.g., separating `lib/` changes from `docs/` changes).
  - Provide a preview of the proposed commit messages.
- **CLI Command**: `vibe commit`

### C. Post-Task Maintenance Workflow
- **Script**: `scripts/task-done.sh`
- **Function**:
  - Run regression tests (using `scripts/test-all.sh`).
  - Perform environment cleanup (equivalent to `scripts/cleanup.sh`).
  - Remind/Prompt the agent to update `MEMORY.md` and `TASK.md`.
- **CLI Command**: `vibe done`

## 4. Technical Requirements
- **Language**: Zsh (consistent with current codebase).
- **Libraries**: Must source `lib/utils.sh` for logging and security utilities.
- **CLI Integration**: Modify `scripts/vibecoding.sh` to include these as subcommands.
- **Documentation**: Update `.agent/workflows/*.md` to reference the new `vibe` commands instead of raw bash blocks.

## 5. Reference
Refer to the existing Implementation Plan (local file) for data structures and script details.
