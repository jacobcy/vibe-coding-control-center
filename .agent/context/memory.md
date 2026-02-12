# MEMORY

## Active Context
- **Project**: Vibe Coding Control Center
- **Status**: Maintenance & Refactoring
- **Current Focus**: Consolidation and Technical Debt Cleanup

## Incidents & Lessons Learned
- **[2026-02-11] Critical Incident: Unrelated Code Modification**
  - **Correction Rule**: **NEVER modify or remove code/comments unrelated to the current feature.** Documentation is functional code for users.


## Key Decisions
- **Language Protocol**: English Thought, Chinese Response (2026-02-10).
- **Architecture**: Modular shell script architecture (`lib/`, `bin/`, `config/`).
- **Installation**: Single entry point `scripts/install.sh` delegating to specialized scripts.
- **Project Positioning**: Configuration management scripts for external AI tools, not AI agent implementation (2026-02-11).
- **Configuration Philosophy**: Priority on **transparency and explicit control**. Avoid excessive automation that masks configuration risks. (2026-02-11).
- **No-Template Rule**: `keys.template.env` must NEVER be used as a fallback for user configuration. If valid config is missing, fail and prompt user for manual setup. (2026-02-11).

## System Context
- **OS**: macOS
- **Shell**: zsh
# Execution Log
[2026-02-10] Implemented /feature-commit workflow.
[2026-02-10] Completed /audit-and-cleanup: reorganized documentation, fixed `vibe-tdd` nounset bug, and consolidated help logic.
[2026-02-11] Configuration system cleanup: unified keys.env, removed VIBE_DEBUG, enhanced documentation.
[2026-02-11] Major Refactor of `vibe config` and `vibe env`:
- **Responsibility Split**: `vibe env` manages `keys.env` (environment variables), while `vibe config` manages AI tool-specific files (OpenCode, Codex).
- **Consolidation**: Moved all `keys.env` logic to a shared `lib/config_init.sh` module, simplifying `install.sh` and `vibe env`.
- **Init to Sync**: Renamed `vibe env init` to `vibe env sync` and removed template fallback to ensure user directory only contains valid, project-synchronized configurations.
[2026-02-11] **Vibe Flow Architecture Refactoring**:
- **Core Positioning Clarified**: Vibe Coding Control Center is a **management and orchestration tool**, NOT an agent implementation tool.
- **What We Manage**: Tool installation, working directories, environment variables, aliases, configuration files, development prompts/templates.
- **What We DON'T Do**: We do NOT implement or replace the work that agents (claude, opencode, codex) complete. We prepare the environment and provide guidance.
- **Refactoring Actions**: 
  - Deleted duplicate `lib/worktree.sh` (188 lines) - functionality already in `aliases.sh`
  - Rewrote `lib/flow.sh` to leverage existing tools (`wtnew`, `vup`, `wtrm` from aliases.sh)
  - Integrated external tools: `gh` (PR management), `lazygit` (code review), `tmux` (workspace)
  - Implemented complete workflow lifecycle: start → spec → test → dev → review → pr → done

- **Design Principle**: "Orchestrate and integrate" rather than "reimplement and replace"

## Concept Clarity (2026-02-11, updated)
- **Path auto-detection**: `VIBE_ROOT` and `VIBE_HOME` are **internal implementation details**, never user-configured.
  - `VIBE_ROOT` is auto-detected from the executing script's location or by walking up from PWD to find a `.vibe/` directory.
  - `VIBE_HOME` is always `$VIBE_ROOT/.vibe` (fixed relationship).
  - `keys.env` only stores **user configuration** (API keys, tool selection, agent identity) — no path variables.

- **Multi-Branch Development Mode**:
  - **Mechanism**: The `vibe` command is context-aware. It walks up from PWD looking for a `.vibe` directory.
  - **Workflow**:
    1. Clone/Worktree a new branch.
    2. Ensure the branch has a `.vibe` folder (synced via `vibe-init` or manual setup).
    3. Running `vibe` inside that folder automatically delegates execution to **that specific branch's** `bin/vibe`.
  - **Benefit**: Allows developing and testing different versions of Vibe core logic simultaneously in different worktrees without conflicts.

