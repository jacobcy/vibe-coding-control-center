# Portability Smoke Test Checklist

**Date**: 2026-05-17
**Related Issues**: #937 (validation), #931 (parent), #932-#936 (implementation)

## Test Matrix

| Profile | Scenario | Expected Behavior | Status |
|---------|----------|-------------------|--------|
| minimal | Empty repo | Creates .vibe/config.yaml with profile: minimal | [ ] |
| minimal | Empty repo | No .agent/ directory created | [ ] |
| minimal | Empty repo | No skills/ directory created | [ ] |
| minimal | Empty repo | No GitHub labels created | [ ] |
| minimal | Empty repo | paths.policies_root = ~/.vibe/assets/policies | [ ] |
| github-flow | GitHub repo | Creates .vibe/config.yaml with profile: github-flow | [ ] |
| github-flow | GitHub repo | Creates .agent/ directory | [ ] |
| github-flow | GitHub repo | Creates GitHub labels (state/*) | [ ] |
| github-flow | GitHub repo | paths.policies_root = ~/.vibe/assets/policies | [ ] |
| vibe-center | This repo | Existing .vibe/config.yaml remains valid | [ ] |
| vibe-center | This repo | Existing .agent/ structure remains | [ ] |
| vibe-center | This repo | Existing skills/ structure remains | [ ] |
| vibe-center | This repo | paths.policies_root = .agent/policies | [ ] |

## Pre-Test Setup

```bash
# Backup current repo state
git stash push -m "pre-smoke-test-backup" || true

# Ensure global assets exist
test -d ~/.vibe/assets || echo "ERROR: Run scripts/install.sh first"
```

## Test 1: Empty Repo (minimal profile)

**Setup**:
```bash
TEMP_REPO=$(mktemp -d)
cd "$TEMP_REPO"
git init
echo "# Test Repo" > README.md
git add README.md
git commit -m "Initial commit"
```

**Execute**:
```bash
vibe init --profile minimal --yes
```

**Verify**:
- [ ] `.vibe/config.yaml` exists and contains `profile: minimal`
- [ ] `.vibe/config.yaml` has `features.agent: false`
- [ ] `.vibe/config.yaml` has `features.local_skills: false`
- [ ] `.vibe/config.yaml` has `features.global_skills: false`
- [ ] `.vibe/config.yaml` has `features.github_labels: false`
- [ ] `.vibe/config.yaml` has `paths.policies_root` pointing to `~/.vibe/assets/policies`
- [ ] No `.agent/` directory created
- [ ] No `skills/` directory created
- [ ] No GitHub labels created

**Cleanup**:
```bash
cd -
rm -rf "$TEMP_REPO"
```

## Test 2: Empty Repo (github-flow profile)

**Setup**:
```bash
TEMP_REPO=$(mktemp -d)
cd "$TEMP_REPO"
git init
echo "# Test Repo" > README.md
git add README.md
git commit -m "Initial commit"
# Create GitHub repo (optional - skip if no gh access)
gh repo create test-smoke --private --source=. --push 2>/dev/null || echo "Skipping GitHub repo creation"
```

**Execute**:
```bash
vibe init --profile github-flow --yes --skip-labels
```

**Verify**:
- [ ] `.vibe/config.yaml` exists and contains `profile: github-flow`
- [ ] `.vibe/config.yaml` has `features.agent: true`
- [ ] `.vibe/config.yaml` has `features.local_skills: false`
- [ ] `.vibe/config.yaml` has `features.global_skills: true`
- [ ] `.vibe/config.yaml` has `features.github_labels: true`
- [ ] `.vibe/config.yaml` has `paths.policies_root` pointing to `~/.vibe/assets/policies`
- [ ] `.agent/` directory created
- [ ] `.agent/workflows/` directory exists
- [ ] `.codex/skills/` directory exists
- [ ] `skills/` directory NOT created (github-flow doesn't need it)

**Cleanup**:
```bash
cd -
rm -rf "$TEMP_REPO"
gh repo delete test-smoke --yes 2>/dev/null || true
```

## Test 3: Current Repo (vibe-center profile - regression)

**Setup**:
```bash
cd /path/to/vibe-center
git status  # Ensure clean working tree
```

**Verify existing state**:
- [ ] `.vibe/config.yaml` exists and contains `profile: vibe-center`
- [ ] `.agent/` directory exists
- [ ] `.agent/policies/` directory exists
- [ ] `.agent/workflows/` directory exists
- [ ] `.codex/skills/` directory exists
- [ ] `skills/` directory exists
- [ ] `.vibe/config.yaml` has `paths.policies_root: .agent/policies`
- [ ] `.vibe/config.yaml` has `paths.prompts_root: config/prompts`

**Optional - Re-run init**:
```bash
vibe init --profile vibe-center --yes --skip-labels
```

- [ ] No destructive changes to existing structure
- [ ] `.vibe/config.yaml` remains valid

## Test 4: ConventionResolver Resolution

**Test that ConventionResolver respects profile**:

```bash
# In vibe-center repo
uv run python -c "
from vibe3.services.convention_resolver import ConventionResolver
resolver = ConventionResolver.from_repo()
convention = resolver.resolve()
assert convention.branch.task_prefix == 'task/issue-'
assert convention.state_label('handoff') == 'state/handoff'
print('Vibe Center profile resolution works')
"
```

- [ ] ConventionResolver correctly resolves vibe-center profile

## Test 5: ProfileConfig Adapter Lookup

**Test that ProfileConfig connects to adapter**:

```bash
uv run python -c "
from vibe3.config.profile_config import ProfileConfig
config = ProfileConfig(profile='vibe-center')
policy_path = config.get_policy_path('plan')
assert policy_path == '.agent/policies/plan.md'
print('ProfileConfig adapter lookup works')
"
```

- [ ] ProfileConfig correctly returns vibe-center adapter resources

## Results Summary

- **Date Executed**: _______________
- **Executor**: _______________
- **Pass/Fail Count**: ___/13
- **Critical Issues**: _______________
- **Follow-up Required**: _______________
