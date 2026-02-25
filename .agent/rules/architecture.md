# Architecture Rules (架构规则)

## Core Principle
**Orchestrate, don't implement.** We manage AI tools, we don't replace them.

## Boundaries
- `bin/vibe`: CLI dispatcher only. No business logic.
- `lib/*.sh`: Self-contained modules. Each ≤200 lines.
- `config/aliases/`: User-facing shell shortcuts. Loaded via `config/aliases.sh`.
- `.agent/`: AI workspace (skills, rules, context). Not shell code.

## Dependencies (外部工具)
| Tool | Purpose | Required |
|------|---------|----------|
| git | Version control, worktrees | Yes |
| tmux | Session management | For `vup`/`vt*` |
| claude | AI agent CLI | For `ccy`/`cwt` |
| opencode | AI agent CLI | Optional |
| codex | AI agent CLI | Optional |
| gh | GitHub CLI | For `vibe flow pr` |
| lazygit | Git TUI | For `vibe flow review` |
| jq | JSON processing | Optional |

## What We Don't Build
See CLAUDE.md §HARD RULES Rule 4 (不做清单) for the complete exclusion list.

## Adding New Features
1. Check SOUL.md — does this align?
2. Check 不做清单 — is this excluded?
3. Verify LOC budget — room for this?
4. If all pass: implement with tests, include LOC diff in PR
