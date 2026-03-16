# 更新日志

## [2.1.34] - 2026-03-16

### ✨ Changed
- Add warning when using 'vibe roadmap list --json --all' without --keywords filter to prevent excessive output. Users can now use --keywords to filter results before JSON output.

## [2.1.33] - 2026-03-15

### 📚 Documentation
- Add comprehensive Vibe 3.0 documentation system with proper frontmatter metadata
- Add implementation guides for architecture, coding standards, logging, and error handling
- Add Python standards document (.agent/rules/python-standards.md)
- Add phase-based execution plans (Phase 01-05) for Vibe 3.0 rebuild
- Remove outdated implementation-spec-phase2.md

## [2.1.32] - 2026-03-13

### ✨ Changed
- Retire worktrees.json runtime state from flow and task paths

## [2.1.31] - 2026-03-13

### ✨ Changed
- Freeze branch-first runtime semantics and task issue vocabulary

## [2.1.30] - 2026-03-13

### ✨ Changed
- isolate serena gate runtime and codify serial split flow

## [2.1.29] - 2026-03-13

### ✨ Changed
- add remote issue dependency commands

## [2.1.28] - 2026-03-12

### ✨ Changed
- feat(roadmap): show roadmap dependency blockers and ready state

## [2.1.27] - 2026-03-12

### ✨ Changed
- fix(flow): keep closeout on a reusable non-detached baseline branch across worktrees

## [2.1.26] - 2026-03-12

### ✨ Changed
- docs(standards): define flow identity main chain ...

## [2.1.25] - 2026-03-12

### ✨ Changed
- docs(plan): add history backfill reconciliation plan ...

## [2.1.24] - 2026-03-12

### ✨ Changed
- docs(plan): add gh-112 cli output summary plan ...

## [2.1.23] - 2026-03-12

### ✨ Changed
- feat(flow): auto-link issues in PR and bridge PRs in roadmap sync.

## [2.1.22] - 2026-03-12

### ✨ Changed
- fix: gate vibe flow done on review evidence ...

## [2.1.21] - 2026-03-12

### ✨ Changed
- fix(roadmap): replace echo with print -r to prevent JSON mangling in Zsh ...

## [2.1.19] - 2026-03-12

### ✨ Changed
- feat(roadmap): support syncing merged PRs into the configured GitHub Project, adding merged PRs to the project when they are missing so roadmap items stay aligned with completed work.

## [2.1.18] - 2026-03-11

### ✨ Changed
- feat: intake vibe-task issues into roadmap sync ...

## [2.1.17] - 2026-03-11

### ✨ Changed
- Define roadmap intake gate and intake view boundaries

## [2.1.16] - 2026-03-11

### ✨ Changed
- Make `vibe roadmap add --help` exit safely without creating roadmap items.
- Shift flow runtime discovery and audit behavior to branch-first semantics, with registry runtime-branch fallback when worktree entries are missing.

## [2.1.15] - 2026-03-11

### ✨ Changed
- Tighten backlog governance and commit preflight

## [2.1.14] - 2026-03-11

### ✨ Changed
- Require explicit plan binding when creating tasks, and standardize agent workflow naming and workflow/skill boundaries.

## [2.1.13] - 2026-03-11

### ✨ Changed
- fix: make flow pr bump commit atomic ...

## [2.1.12] - 2026-03-11

### ✨ Changed
- fix: remove flow-new worktree semantics ...

## [2.1.11] - 2026-03-11

### ✨ Changed
- test commit ...

## [2.1.10] - 2026-03-11

### ✨ Changed
- Align GitHub Project orchestration semantics and handoff governance rules

## [2.1.9] - 2026-03-10

### ✨ Changed
- Rename `vibe-skill` to `vibe-skill-audit`.
- Rename `vibe-skills` to `vibe-skills-manager`.
- Align task/flow runtime to resolve worktree roots via `git rev-parse --show-toplevel`.
- Remove worktree-local `.vibe/*` cache usage in favor of shared-state-first task resolution.

## [2.1.8] - 2026-03-10

### ✨ Changed
- Align task/flow worktree root semantics and skill routing.

## [2.1.7] - 2026-03-10

### ✨ Changed
- refactor(flow): split tests and make switch carry dirty state safely ...

## [2.1.6] - 2026-03-08

### ✨ Changed
- refactor: decouple physical git signature from logical authorship log ...

## [Unreleased]

### ✨ New Features
- **Task Registry Audit & Repair**: Comprehensive task registration audit and automatic repair system.
  - **Three-Phase Audit**: Data quality → Deterministic checks → Semantic analysis
  - **Data Quality Repair**: Auto-fix null branch fields in worktrees.json
  - **Branch Registration Check**: Detect unregistered task branches
  - **OpenSpec Sync Check**: Identify unsynced OpenSpec changes
  - **PR Semantic Analysis**: AI-powered task detection from merged PRs
  - **Document Scanning**: Detect tasks in docs/plans and docs/prds
- **vibe check Integration**: Task audit now integrates with `vibe check --audit-tasks`
  - **Closed-Loop Workflow**: Repair tasks before project audit
  - **Phase 0 Addition**: Task audit runs as Phase 0 in vibe check
- **Interactive Repair**: Three user interaction modes
  - **Batch Mode**: Auto-repair high-confidence issues
  - **Individual Mode**: Confirm each repair step-by-step
  - **View-Only Mode**: Preview issues without making changes

### 🔧 Technical Details
- **Architecture**: Strict three-layer separation (Shell → Skill → User)
- **Shell Layer**: Deterministic data operations, no AI decisions
- **Skill Layer**: Semantic analysis, intelligent suggestions, user interaction
- **User Layer**: Final confirmation and decision authority
- **Backup Strategy**: Automatic backup before repairs (worktrees.json.backup)
- **Validation**: Post-repair verification with rollback on failure

### 📊 Completion Metrics
- **Section 1-8**: Core functionality complete (48/79 tasks, 61%)
- **Shell Layer**: 100% complete (all audit commands functional)
- **Skill Layer**: 100% complete (full audit workflow with AI analysis)
- **Integration**: 100% complete (vibe check --audit-tasks working)

## [2.1.5] - 2026-03-07

### ✨ New Features
- **Smart Task Sync**: Upgraded `vibe check` to intelligently sync task status based on PR merged events.
  - **Phase 2**: Detect merged PRs and analyze task completion using AI (Subagent)
  - **Phase 3**: Confidence-based processing (high/medium/low) with user confirmation
  - **Phase 4**: Deep code analysis option for uncertain tasks
  - **Graceful Degradation**: Continue static checks when `gh` CLI is unavailable
- **Flow Commands**: Enhanced `vibe flow` command family
  - `vibe flow list --pr`: Query last 10 branches with PRs
  - `vibe flow list --keywords <text>`: Filter branches by keyword
  - `vibe flow review <branch> --json`: Return structured PR data for programmatic use

### 🔧 Technical Details
- **Architecture**: Three-tier implementation (Shell → Skill → Subagent)
- **Data Strategy**: Real-time query via `gh`, no local PR caching
- **User Control**: AI suggests, human confirms - preserves decision authority
