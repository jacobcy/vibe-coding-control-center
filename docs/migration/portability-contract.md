# Vibe3 Portability Contract

**Version**: 3.0
**Last Updated**: 2026-05-17
**Related**: [Design Doc](../plans/2026-05-16-vibe3-portability-decoupling-design.md)

## Purpose

This document defines the portability contract for Vibe3, including:
- Resource precedence rules
- Migration guidance from legacy install/init flows
- Known non-goals and remaining repo-specific assumptions

## Resource Precedence Rules

Vibe3 uses a **strict precedence order** for resolving resources. Higher priority sources **shadow** lower priority sources.

### 1. Repo-local explicit path (highest priority)

If a path is explicitly configured in `.vibe/config.yaml` or via CLI args, it takes absolute precedence.

```yaml
# .vibe/config.yaml
paths:
  policies_root: /custom/path/policies  # Takes precedence over everything
```

### 2. Repo-local `.vibe/` overlay

If no explicit path is set, Vibe3 checks for repo-local overlays:

```
.vibe/
  policies/
    plan.md       # Overrides ~/.vibe/assets/policies/plan.md
  prompts/
    prompts.yaml  # Overrides ~/.vibe/assets/prompts/prompts.yaml
```

**Use case**: Project-specific policy overrides without modifying global assets.

### 3. Profile adapter resources

If no repo-local overlay exists, Vibe3 queries the profile's adapter:

```python
# ConventionResolver → ProfileConfig → AdapterManifest
resolver = ConventionResolver.from_repo()
policy_path = resolver.get_policy_path("plan")
# Returns: .agent/policies/plan.md (vibe-center profile)
# Returns: ~/.vibe/assets/policies/plan.md (minimal profile)
```

**Profiles**:
- **vibe-center**: Uses repo-local resources (`.agent/`, `config/prompts/`, `skills/`)
- **minimal**: Uses global assets (`~/.vibe/assets/`)
- **github-flow**: Uses global assets with `.agent/` structure

### 4. User-global `~/.vibe/assets` (fallback)

If the profile has no adapter or the adapter doesn't provide the resource:

```
~/.vibe/assets/
  policies/
    common.md
    plan.md
    run.md
    review.md
  prompts/
    prompts.yaml
    prompt-recipes.yaml
  templates/
    init/
      minimal/
      github-flow/
      vibe-center/
```

### 5. Package builtin defaults (lowest priority)

If no other source exists, Vibe3 falls back to package builtin defaults.

**Note**: Currently, most resources rely on `~/.vibe/assets` being populated by `scripts/install.sh`. Package builtin defaults are minimal.

## Asset Resolution Example

**Scenario**: Resolving `plan.md` policy path in different profiles

### vibe-center profile:
1. Check `.vibe/config.yaml` → Not set
2. Check `.vibe/policies/plan.md` → Not found
3. Check adapter (vibe-center) → Returns `.agent/policies/plan.md`
4. **Result**: `.agent/policies/plan.md`

### minimal profile:
1. Check `.vibe/config.yaml` → Not set
2. Check `.vibe/policies/plan.md` → Not found
3. Check adapter (none for minimal) → No adapter
4. Check `~/.vibe/assets/policies/plan.md` → Found
5. **Result**: `~/.vibe/assets/policies/plan.md`

## Provenance Tracking

Vibe3 logs the source of each resolved resource:

```python
from loguru import logger

# ConventionResolver logs resolution steps
logger.debug("Resolving policy 'plan'")
logger.debug("  1. .vibe/config.yaml: not set")
logger.debug("  2. .vibe/policies/plan.md: not found")
logger.debug("  3. Adapter vibe-center: .agent/policies/plan.md")
logger.info("Resolved policy 'plan' → .agent/policies/plan.md")
```

## Migration Guide

### From Legacy `scripts/init.sh`

**Before (v2)**:
```bash
scripts/init.sh
# - Hardcoded to create .agent/, skills/, .claude/
# - No profile selection
# - Assumed Vibe Center repo structure
```

**After (v3)**:
```bash
# For new projects
vibe init --profile minimal      # Minimal runtime
vibe init --profile github-flow  # GitHub orchestration

# For vibe-center repo (no change needed)
# Existing structure remains valid
```

### Key Differences

| Aspect | v2 init.sh | v3 vibe init |
|--------|-----------|-------------|
| Profile selection | None | Required (`--profile`) |
| .agent/ creation | Always | Profile-dependent |
| skills/ creation | Always | Profile-dependent |
| GitHub labels | Always | Profile-dependent |
| Config file | None | `.vibe/config.yaml` |
| Portability | Low | High |

### Migration Steps

**Case 1: Existing Vibe Center repo**
- No action required
- `.vibe/config.yaml` should already exist
- All existing resources remain valid

**Case 2: New project wanting GitHub flow**
```bash
git init
vibe init --profile github-flow --yes
# Creates .agent/, .vibe/config.yaml, GitHub labels
```

**Case 3: New project wanting minimal runtime**
```bash
git init
vibe init --profile minimal --yes
# Creates .vibe/config.yaml only
# Uses global assets from ~/.vibe/assets
```

## Known Non-Goals

The following are **explicitly out of scope** for the current portability implementation:

### 1. Cross-repo skill sharing

Vibe3 does **not** support installing skills from other repositories. Skills must be either:
- Global: `~/.vibe/skills/vibe-*` (installed by `scripts/install.sh`)
- Repo-local: `skills/<name>/SKILL.md` (vibe-center profile only)

**Rationale**: Skills encode repo-specific workflows. Cross-repo sharing requires a skill registry and versioning system, which is future work.

### 2. Automatic profile detection from repo metadata

Vibe3 requires explicit `--profile` selection or `VIBE_PROFILE` env var. It does **not** auto-detect profile from:
- Repo structure (e.g., presence of `.agent/`)
- GitHub repo metadata
- File contents

**Rationale**: Explicit profile selection prevents accidental misconfiguration.

### 3. `.vibe/config.yaml` runtime wiring

`.vibe/config.yaml` is currently **decorative only** - it's generated by `vibe init` but not yet wired to runtime configuration loading.

**Future work**: `VibeConfig` should load `.vibe/config.yaml` as the first precedence layer.

**Tracking**: Issue #983

### 4. Profile switching after initialization

Vibe3 does **not** support changing profile after `vibe init`:
- Cannot convert from `minimal` → `github-flow`
- Cannot convert from `github-flow` → `vibe-center`

**Rationale**: Profile change may require creating/deleting directories and resources, which is destructive.

**Workaround**: Re-run `vibe init --profile <new>` with caution, or manually adjust `.vibe/config.yaml`.

## Remaining Repo-Specific Assumptions

Despite portability efforts, some assumptions remain:

### 1. Git repository required

Vibe3 requires the project to be a Git repository:
- `vibe init` fails if not in a Git repo
- Flow/task commands require Git branches

### 2. GitHub CLI for orchestration features

Profiles with `github_orchestration: true` require:
- `gh` CLI installed
- GitHub repository with `origin` remote
- `gh auth status` passing

### 3. ConventionResolver git remote heuristic

ConventionResolver uses `git remote get-url origin` to detect `vibe-center` profile:
- Relies on repo name containing "vibe-center" or "vibe-coding-control-center"
- May misclassify forks or renamed repos

**Future work**: Explicit profile setting via `.vibe/config.yaml` or `VIBE_PROFILE`.

### 4. Hardcoded paths in shell scripts

Some shell scripts (e.g., `lib/worktree.sh`) still contain hardcoded paths:
- `lib/alias/`
- `lib/keys_support.sh`

**Tracking**: Issue #983

## Testing Your Setup

Run the smoke tests to validate your setup:

```bash
# See docs/validation/smoke-tests.md for detailed checklist
vibe doctor  # Check environment
vibe init --profile <name> --yes  # Test initialization
```

## Troubleshooting

### "Global assets not found"

**Symptom**: `vibe init` warns about missing `~/.vibe/assets`

**Solution**: Run the installation script:
```bash
scripts/install.sh
```

### "Profile not recognized"

**Symptom**: ConventionResolver returns unexpected results

**Solution**: Set profile explicitly:
```bash
export VIBE_PROFILE=vibe-center
# or
vibe init --profile vibe-center --yes
```

### "GitHub labels creation failed"

**Symptom**: `vibe init` fails to create labels

**Solution**: Check GitHub CLI authentication:
```bash
gh auth status
```

Or skip label creation:
```bash
vibe init --profile github-flow --skip-labels
```

## References

- [Portability Design Doc](../plans/2026-05-16-vibe3-portability-decoupling-design.md)
- [ConventionResolver Source](../../src/vibe3/services/convention_resolver.py)
- [ProfileConfig Source](../../src/vibe3/config/profile_config.py)
- [Adapter System](../../src/vibe3/adapters/)
