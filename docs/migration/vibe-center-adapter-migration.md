# Vibe Center Adapter Migration

## Overview

As of PR #982 (Issue #936), Vibe Center repository is now an explicit adapter consumer instead of relying on implicit repo-local paths.

## What Changed

### Before (Implicit)
```
Code directly reads:
- .agent/policies/plan.md
- skills/vibe-commit/SKILL.md
- supervisor/apply.md
```

**Assumption**: "Because these files exist in this repo, they're always available."

### After (Explicit)
```
Code reads through profile resolution:
- ConventionResolver.get_policy_path("plan")
- ConventionResolver.get_skill_path("vibe-commit")
- ConventionResolver.get_supervisor_path("apply")
```

**Guarantee**: Only resources declared in adapter manifest are available.

## Impact on Current Repo

### For Developers

No immediate action required. `.vibe/config.yaml` is committed to repo.

If you want to use minimal profile for testing:

```bash
export VIBE_PROFILE=minimal
vibe3 flow show  # Will show minimal profile (no policies, no supervisor)
```

### For External Projects

When using vibe3 in external projects:

1. **Minimal profile** (default):
   - No policies loaded
   - No skills available
   - No supervisor
   - Branch prefix: `issue-`

2. **Vibe Center profile**:
   ```bash
   vibe init --profile vibe-center
   ```
   - All policies from vibe-center adapter
   - Skills (vibe-commit, vibe-review, etc.)
   - Supervisor governance
   - Branch prefix: `task/issue-`

## Adapter Manifest

Vibe Center adapter declares:

- **Policies**: plan.md, run.md, review.md, common.md
- **Supervisor templates**: apply.md, governance workflows
- **Skills**: Auto-discovered from `skills/` directory
- **Workflows**: Auto-discovered from `.agent/workflows/`

## Configuration File

`.vibe/config.yaml` format:

```yaml
profile: vibe-center  # or minimal, github-flow
adapter: vibe-center  # explicit adapter selection
overrides:
  # Optional per-repo customizations
```

## Breaking Changes

### For Code in This Repo

If you added new code that hardcodes `.agent/` or `skills/` paths, **update to use profile resolution**:

```python
# BEFORE
path = ".agent/policies/custom.md"

# AFTER
resolver = ConventionResolver.from_repo()
path = resolver.get_policy_path("custom")
if not path:
    raise ValueError("Custom policy not available in current profile")
```

### For External Consumers

If you were copying Vibe Center repo structure:

- **Stop**: Don't copy `.agent/` or `skills/` directories
- **Use**: `vibe init --profile vibe-center` to get clean setup
- **Customize**: Override specific files in `.vibe/` overlay

## References

- Issue #936: Extract Vibe Center adapter
- Issue #935: Remove repo-bound defaults from core
- Issue #933: AssetResolver with layered lookup
- Design Doc: `docs/plans/2026-05-16-vibe3-portability-decoupling-design.md`