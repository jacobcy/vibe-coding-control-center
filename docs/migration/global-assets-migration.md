# Migration Guide: Global Runtime Assets

## Overview

Vibe3 CLI now uses a layered asset lookup system with user-global runtime assets under `~/.vibe/assets/`.

## What Changed

**Before:**
- All runtime resources loaded from repo-relative paths
- Installing CLI didn't bring runtime assets
- Required Vibe Center repo for operation

**After:**
- Generic assets stored in `~/.vibe/assets/`
- Layered lookup: repo-local → global → builtin
- CLI can operate in any Git repo

## Migration Steps

### 1. Sync Global Assets

```bash
vibe3 assets sync
```

This copies builtin assets to `~/.vibe/assets/`.

### 2. Verify Asset Resolution

Check where prompts are loaded from:

```bash
vibe3 assets status
```

### 3. Override Global Assets (Optional)

To use repo-local prompts instead of global:

1. Create `config/prompts/prompts.yaml` in your repo
2. Resolver will prioritize repo-local files

### 4. Update Custom Tooling

If your tooling directly loads `config/prompts/prompts.yaml`:

```python
# Before
prompts_path = Path("config/prompts/prompts.yaml")

# After
from vibe3.assets import get_asset_resolver

resolver = get_asset_resolver()
prompts_path = resolver.resolve("prompts/prompts.yaml")
```

## Asset Types

| Type | Global Path | Repo-Local Override |
|------|-------------|---------------------|
| Prompts | `~/.vibe/assets/prompts/` | `config/prompts/` |
| Policies | `~/.vibe/assets/policies/` | `.agent/policies/` |
| Models | `~/.vibe/assets/models/` | `config/v3/models.json` |
| Skills | `~/.vibe/assets/manifests/` | `config/v3/skills.json` |

## Troubleshooting

### Assets not found

Run `vibe3 assets sync` to install global assets.

### Wrong asset version

Check manifest: `cat ~/.vibe/assets/manifest.json`

### Need to force update

```bash
rm -rf ~/.vibe/assets
vibe3 assets sync
```
