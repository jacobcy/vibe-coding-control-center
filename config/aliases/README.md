# Config/Aliases Reference

## Overview

This directory contains alias modules for Vibe Center commands, organized by functionality.

## V3 Execution Plane Modules

### worktree.sh
Worktree management commands for V3 Execution Plane.

**Commands**:
- `wtnew <task-slug> [agent] [base]` - Create worktree with auto-naming
- `wtlist [owner] [task]` - List worktrees with filtering
- `wtvalidate <worktree>` - Validate worktree integrity
- `wtrm <worktree> [--force]` - Remove worktree
- `wt <worktree>` - Jump to worktree

**Naming Convention**: `wt-<owner>-<task-slug>`

### tmux.sh
Tmux session management for V3 Execution Plane.

**Commands**:
- `tmnew <task-slug> [agent]` - Create session with auto-naming
- `tmattach [session]` - Attach to session (auto-detect)
- `tmlist` - List sessions with task context
- `tmswitch <session>` - Switch between sessions
- `tmkill <session> [--force]` - Kill session
- `tmrename <old> <new>` - Rename session

**Naming Convention**: `<agent>-<task-slug>`

### execution-contract.sh
Execution result persistence and querying.

**Functions**:
- `write_execution_result <task_id> <worktree> <session>` - Write result
- `query_by_task_id <task_id>` - Query by task ID
- `query_by_worktree <worktree>` - Query by worktree
- `query_by_session <session>` - Query by session
- `update_execution_result <task_id> <field> <value>` - Update result
- `cleanup_execution_results` - Cleanup old results

**Storage**: `.agent/execution-results/<task_id>.json`

### session-recovery.sh
Session recovery and restoration commands.

**Commands**:
- `wtrecover --task-id <id>` - Recover by task ID
- `wtrecover --worktree <path>` - Recover by worktree
- `wtrecover --session <name>` - Recover by session
- `wtrecover-history [task-id]` - View recovery history

**Recovery Time**: < 30 seconds

## Legacy V2 Modules

### git.sh
Basic git workflow aliases.

### claude.sh
Claude Code specific aliases.

### vibe.sh
Vibe command aliases.

## Usage

All aliases are auto-loaded when sourcing `config/aliases.sh`:

```bash
source config/aliases.sh
```

Or add to your `.zshrc`:

```zsh
source /path/to/vibe-center/config/aliases.sh
```

## Adding New Aliases

1. Create module file: `config/aliases/<module>.sh`
2. Add to `config/aliases.sh`:
   ```bash
   source "${aliases_dir}/<module>.sh"
   ```
3. Follow naming conventions and CLAUDE.md HARD RULES

## Testing

Each module should have corresponding tests in `tests/test_<module>.bats`.

## Documentation

For V3 Execution Plane commands, see:
- `.agent/rules/execution-plane.md` - Usage rules
- `skills/execution-plane/README.md` - Detailed guide
- `skills/execution-plane/SKILL.md` - Skill definition
