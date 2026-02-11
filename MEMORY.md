# MEMORY

## Active Context
- **Project**: Vibe Coding Control Center
- **Status**: Maintenance & Refactoring
- **Current Focus**: Consolidation and Technical Debt Cleanup

## Key Decisions
- **Language Protocol**: English Thought, Chinese Response (2026-02-10).
- **Architecture**: Modular shell script architecture (`lib/`, `bin/`, `config/`).
- **Installation**: Single entry point `scripts/install.sh` delegating to specialized scripts.
- **Project Positioning**: Configuration management scripts for external AI tools, not AI agent implementation (2026-02-11).

## System Context
- **OS**: macOS
- **Shell**: zsh
# Execution Log
[2026-02-10] Implemented /feature-commit workflow.
[2026-02-10] Completed /audit-and-cleanup: reorganized documentation, fixed `vibe-tdd` nounset bug, and consolidated help logic.
[2026-02-11] Configuration system cleanup: unified keys.env, removed VIBE_DEBUG, enhanced documentation.
