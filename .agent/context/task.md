# TASK

## Current Objectives

- [ ] [TASK-002] Maintain test coverage > 90%. (Current: 100%, 46/46 passing)
  - FIXED: config_loader.sh readonly variable issue resolved
  - New test: test_cli_commands.sh (46 test cases, comprehensive CLI coverage)

## Backlog

- [ ] [context-20260221-004] 与 /learn 集成
  - Context: 来自 [memory/context-commands.md](memory/context-commands.md)
  - Created: 2026-02-21
- [ ] [TASK-007] Refactor `lib/utils.sh` into smaller modules.
- [ ] [TASK-008] Add CI/CD pipeline configuration.
- [ ] [BUG-config-001] Fix config_loader.sh readonly variable conflict
  - Fixed: 2026-02-22 (added guard to check if variables already defined)
  - Result: 46/46 tests pass (100%)

## Completed
- [x] [TASK-006] Fix CLI code to pass updated tests.
  - Fixed: vibe-chat return→exit, vibe-help exit code, vibe-env help, vibe-help sign command
  - Completed: 2026-02-22
- [x] [TASK-005] Audit CLI code vs command standard and update tests.
  - Generated audit report with 11 findings
  - Completed: 2026-02-22
- [x] [TASK-002-Phase1] Created test_cli_commands.sh with comprehensive CLI tests.
  - 40 test cases covering exit codes, help entry points, command dispatch
  - Completed: 2026-02-22
- [x] [context-20260221-003] 实现 /check 技能（验证记忆一致性）
  - Context: 来自 [memory/context-commands.md](memory/context-commands.md)
  - Created: 2026-02-21
- [x] [context-20260221-002] 实现 /continue 技能 ✅
  - Context: 来自 [memory/context-commands.md](memory/context-commands.md)
  - Created: 2026-02-21
- [x] [context-20260221-001] 实现 /save 技能 ✅
  - Context: 来自 [memory/context-commands.md](memory/context-commands.md)
  - Created: 2026-02-21
- [x] [save-20260221-008] 修复 Skill 格式使其被 Claude Code 识别
- [x] [TASK-012] Add integration tests for configuration loading with strict mode (set -e) to prevent regressions.
- [x] [TASK-001] Implement new features defined in `UPGRADE_FEATURES.md`.
- [x] [TASK-003] Update `docs/standards/COMMAND_STANDARD.md` with help/parameter/exit-code/output format norms.
- [x] [TASK-004] Refactor `docs/tech/COMMAND_STRUCTURE.md` as implementation detail aligned to standard.
- [x] [TASK-009] Consolidate installation scripts.
- [x] [TASK-010] Standardize project documentation structure (Audit 20260210-1804).
- [x] [TASK-011] Clean up legacy tech debt in `bin/vibe` and `lib/config.sh`.
