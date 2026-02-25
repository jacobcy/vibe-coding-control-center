# Memory (长期记忆)

Key decisions and architectural choices for Vibe Center 2.0.

## Architecture Decisions

### 2026-02-25: V2 Rebuild
- **Decision**: Rebuild from scratch with ≤1,200 line budget
- **Rationale**: V1 grew to 5,000+ lines with significant dead code (断路器, 缓存, i18n, NLP路由)
- **Approach**: Governance rules embedded in CLAUDE.md, not shell tools

### Design Principles
- Worktree isolation: `wt-<agent>-<feature>` naming convention
- `vibe_main_guard` protects main/master branches from agent execution
- `keys.env` + `.gitignore` for secret management
- `bin/vibe` dispatcher + `lib/*.sh` modular pattern
- `vibe flow` lifecycle: start → review → pr → done
