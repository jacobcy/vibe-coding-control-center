# Project Context: Vibe Center 2.0

## Project Overview
Vibe Center 2.0 is a **minimalist orchestration tool** for AI-assisted development.
It follows the "Cognition First" principle from [SOUL.md](SOUL.md).

### Core Identity: What We ARE
- **Install & manage AI tools** (claude, opencode, codex)
- **Manage working directories** (worktrees, tmux sessions)
- **Manage API keys** (keys.env)
- **Provide shell aliases** (shortcuts for common workflows)
- **Orchestrate dev lifecycle** (start → review → PR → done)

### Core Identity: What We are NOT
We do **NOT** reimplement agent functionality. See §HARD RULES below.

## Build & Test
- CLI entry: `bin/vibe`
- Diagnostics: `bin/vibe check`
- Workflow: `bin/vibe flow <start|review|pr|done|status>`
- Keys: `bin/vibe keys <list|set|get|init>`
- Install tools: `bin/vibe equip`
- Aliases: `source config/aliases.sh`

## Tech Stack
- **Language**: Zsh scripting (macOS / Linux)
- **Pattern**: `bin/vibe` dispatcher → `lib/*.sh` modules
- **Aliases**: `config/aliases.sh` → `config/aliases/*.sh`
- **Config**: `config/keys.env` (gitignored) + `keys.template.env`

## Project Structure
```
bin/vibe               # CLI dispatcher (~60 lines)
lib/
  utils.sh             # Logging, validation, command helpers
  config.sh            # VIBE_ROOT detection, keys loading
  check.sh             # Environment diagnostics
  equip.sh             # Tool installation
  keys.sh              # API key management
  flow.sh              # Dev workflow lifecycle
config/
  aliases.sh           # Alias loader
  keys.template.env    # Key template
  aliases/             # Alias sub-files (worktree, tmux, claude, etc.)
.agent/                # Agent workspace (skills, rules, context)
```

## Coding Standards
- Source `lib/utils.sh` for shared functions
- Use `log_info`, `log_warn`, `log_error`, `log_step`, `log_success` for output
- Use `validate_path` before file operations
- Use `vibe_has`, `vibe_require`, `vibe_find_cmd` for command checks
- Use `set -e` in scripts for fail-fast
- Think in English, **respond to users and generate reports in Chinese**
- Temporary files go in `temp/` (gitignored)

## Language Protocol
- Think in English.
- **Always respond to the user and generate reports in Chinese.**

---

## HARD RULES (治理规则)

These rules are **mandatory** for all contributors and AI agents.

### Rule 1: LOC Ceiling
`lib/` + `bin/` total lines ≤ **1,200**. Exceeding triggers an audit.
```bash
find lib/ bin/ -name '*.sh' -o -name 'vibe' | xargs wc -l  # must be ≤ 1,200
```

### Rule 2: Single File Limit
Any `.sh` file ≤ **200 lines**. Exceeding requires split.

### Rule 3: Zero Dead Code
Every function must have ≥1 caller. Defined-but-unused functions are forbidden.

### Rule 4: 不做清单 (Scope Gate)
Do NOT implement any of the following:
- ❌ NLP intent routing / chat router
- ❌ Circuit breaker / exponential backoff
- ❌ TTL cache system
- ❌ i18n / multi-language support
- ❌ Custom test framework (use bats-core)
- ❌ Email validation
- ❌ Config migration system
- ❌ JSON state machine
- ❌ Shell-level injection protection (we're not a web server)
- ❌ Shell governance tools (governance.yaml, scope-gate, etc.)

### Rule 5: Tool First
Need tests? Use `bats-core`. Need JSON? Use `jq`. Need HTTP? Use `curl`. Don't reinvent.

### Rule 6: New Feature Gate
Before adding any feature, ask: "Does SOUL.md say we should do this?"
If the answer is not a clear YES, don't do it.

### Rule 7: PR LOC Diff
Every PR description must include `wc -l` before/after comparison:
```
## LOC Diff
Before: lib/+bin/ = XXX lines
After:  lib/+bin/ = YYY lines
Delta:  +/-ZZ lines
```

---

## Key Variables
- `VIBE_ROOT`: Project root directory
- `VIBE_BIN`, `VIBE_LIB`, `VIBE_CONFIG`: Subdirectory paths
- `VIBE_SESSION`: tmux session name (default: "vibe")
- `VIBE_DEFAULT_TOOL`: Default agent tool (default: "claude")

## Linked Docs
- [AGENTS.md](AGENTS.md) — Agent entry point
- [SOUL.md](SOUL.md) — Constitution and principles
- [.agent/README.md](.agent/README.md) — Agent workspace docs
