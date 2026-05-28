# Global Install/Update Model

> Last updated: 2026-05-28
> Related: Issue #1571

## Overview

Vibe Center uses a two-tier distribution model:

1. **Repo-local**: Source code in worktree (immediate effect for development)
2. **Global distribution**: `~/.vibe` (shared across projects)

## Installation Lifecycle

### First-time Setup: `scripts/install.sh`

**Responsibilities:**
- Bootstrap global directory (`~/.vibe`)
- Install uv and Python dependencies
- Configure shell loader (`~/.zshrc`)
- Initialize project/worktree environment (`scripts/init.sh`)

**Does NOT:**
- Perform editable install (removed in #1571)
- Sync global distribution (handled by `vibe update`)

**When to run:**
- Fresh install
- Major version upgrade
- After `scripts/uninstall.sh`

### Global Update: `vibe update`

**Responsibilities:**
- Sync V2/V3 core components to `~/.vibe`
- Clean stale files
- Preserve user configs (`config/keys.env`, `settings.yaml`)
- Idempotent operation

**When to run:**
- After pulling upstream changes
- After updating V2/V3 source code
- When global commands don't match repo version

**Usage:**
```bash
vibe update run           # Normal sync
vibe update run --dry-run # Preview changes
vibe update run --verbose # Detailed output
```

### Project Initialization: `scripts/init.sh`

**Responsibilities:**
- Worktree-specific setup
- Install third-party skills
- Configure symlinks

**When to run:**
- After creating new worktree
- Automatically called by `vibe flow start`

## Effect Semantics

### V2 Shell Changes

| Change Location | Effect | How to Apply |
|----------------|--------|--------------|
| `lib/*.sh` in current worktree | **Immediate** in worktree | Use `bin/vibe` or `vibe3` from worktree |
| `lib/*.sh` globally | Requires sync | Run `vibe update` |
| `config/shell/loader.sh` | Requires reload | `source ~/.zshrc` or restart shell |
| `config/shell/aliases.sh` | Requires reload | `vibe alias` or restart shell |

### V3 Python Changes

| Change Location | Effect | How to Apply |
|----------------|--------|--------------|
| `src/vibe3/*.py` in current worktree | **Immediate** (editable install) | `uv run python src/vibe3/cli.py` |
| `src/vibe3/*.py` globally | Requires sync | Run `vibe update` |
| `pyproject.toml` dependencies | Requires reinstall | `uv sync --all-extras` |

### Configuration Changes

| Change Location | Effect | How to Apply |
|----------------|--------|--------------|
| `config/keys.env` (project) | Immediate in worktree | Restart agent or reload |
| `config/keys.env` (global) | Immediate globally | Restart shell or agent |
| `settings.yaml` (global) | Immediate globally | N/A |

## Distribution Paths

```
Source (Repo/Worktree)         Target (Global)
├─ bin/vibe                 →  ~/.vibe/bin/vibe
├─ bin/vibe3                →  ~/.vibe/bin/vibe3
├─ lib/*.sh                 →  ~/.vibe/lib/
├─ lib3/vibe.sh             →  ~/.vibe/lib3/vibe.sh
├─ src/vibe3/*.py           →  ~/.vibe/src/vibe3/
├─ config/shell/loader.sh   →  ~/.vibe/config/shell/loader.sh
├─ config/keys.template.env →  ~/.vibe/config/keys.env (first time only)
├─ pyproject.toml           →  ~/.vibe/pyproject.toml
└─ uv.lock                   →  ~/.vibe/uv.lock

Preserved (not overwritten):
├─ ~/.vibe/config/keys.env
└─ ~/.vibe/settings.yaml
```

## Troubleshooting

### Global commands don't match repo version

**Symptom:** Running `vibe` from worktree uses old version

**Cause:** Global distribution out of sync

**Solution:**
```bash
vibe update run
source ~/.zshrc
```

### Stale files in ~/.vibe

**Symptom:** Old files lingering after updates

**Cause:** Previous `cp -R` installs didn't clean up

**Solution:**
```bash
vibe update run  # Cleanup is automatic
```

### Editable install confusion

**Symptom:** Not sure if Python changes are effective

**Explanation:** V3 uses editable install for repo-local runs:
- Worktree: `uv run python src/vibe3/cli.py` → immediate effect
- Global: `~/.vibe/bin/vibe3` → requires `vibe update`

**Recommendation:** Use worktree-local `bin/vibe3` for development