# MEMORY

## Active Context
- **Project**: Vibe Coding Control Center
- **Status**: Maintenance & Refactoring
- **Current Focus**: Consolidation and Technical Debt Cleanup

## Incidents & Lessons Learned
- **[2026-02-11] Critical Incident: Unrelated Code Modification**
  - **Correction Rule**: **NEVER modify or remove code/comments unrelated to the current feature.** Documentation is functional code for users.


## Topic Index
| Topic | Last Updated | Summary |
|-------|--------------|---------|
| [cli-testing](memory/cli-testing.md) | 2026-02-22 | CLI 命令测试框架和覆盖率提升 |
| [context-commands](memory/context-commands.md) | 2026-02-21 | 上下文管理命令体系：/save, /continue, /check |

## Key Decisions
- **Language Protocol**: English Thought, Chinese Response (2026-02-10).
- **Architecture**: Modular shell script architecture (`lib/`, `bin/`, `config/`).
- **Installation**: Single entry point `scripts/install.sh` delegating to specialized scripts.
- **Project Positioning**: Configuration management scripts for external AI tools, not AI agent implementation (2026-02-11).
- **Configuration Philosophy**: Priority on **transparency and explicit control**. Avoid excessive automation that masks configuration risks. (2026-02-11).
- **No-Template Rule**: `keys.template.env` must NEVER be used as a fallback for user configuration. If valid config is missing, fail and prompt user for manual setup. (2026-02-11).
- **/save Implementation Strategy**: Iterative approach - Skill → Hooks → Plugin (2026-02-21).

## System Context
- **OS**: macOS
- **Shell**: zsh
- **Tooling**:
  - **ShellCheck**: Installed for static analysis of shell scripts (2026-02-12).

# Execution Log
[2026-02-22] **CLI Code Audit & Testing**:
- **TASK-005**: 审计 CLI 命令，发现 11 个问题（退出码、帮助输出等）
- **TASK-006**: 修复 vibe-chat (return→exit), vibe-help (exit 1→2), vibe-env (帮助统一), vibe-help (添加 sign)
- **TASK-002 Phase1**: 创建 test_cli_commands.sh (40 测试用例)
- **发现**: BUG-config-001 (config_loader.sh readonly 变量冲突)
- **覆盖率**: 71% (17/24 测试通过)
[2026-02-21] **Skill 格式修复**:
- **问题**: /save 和 /continue skills 不被 Claude Code 识别
- **解决**: 将 description 改为英文 + 创建 plugin.json + 符号链接到 ~/.claude/skills/
- **新增**: save-20260221-008 (修复 Skill 格式) ✅
[2026-02-21] **/save Command P1 Implementation**:
- **Completed**: PreToolUse 会话计数器 (.claude/hooks/session-counter.sh)
- **Completed**: Stop Hook 提醒机制 (.claude/hooks/save-reminder.sh)
- **Completed**: Hooks 配置文件 (.claude/hooks/hooks.json)
- **Status**: P0 + P1 完成，待续 P2 (与 /learn 集成) 和 Plugin 包装
[2026-02-21] **/save Command P0 Implementation**:
- **Completed**: /save Skill 核心逻辑 (.agent/skills/save/SKILL.md)
- **Completed**: memory/ 目录结构 (.agent/context/memory/)
- **Completed**: memory.md Topic Index 扩展
- **Strategy**: 迭代式实现 - Skill → Hooks → Plugin
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
[2026-02-12] **Tooling Update**:
- **ShellCheck**: Validated installation and updated coding standards to mandate static analysis.

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
