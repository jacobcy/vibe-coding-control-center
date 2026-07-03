# Publish Directive: Issue #3240 — direnv whitelist

## Current State
- Issue: #3240 — 自动配置 direnv whitelist（install.sh + vibe init）
- Branch: task/issue-3240
- Commit: 5320a060 (feat(install): add direnv whitelist for ~/.vibe directory)
- Scope: scripts/install.sh + tests/vibe2/integration/test_install_gh_noninteractive.bats
- All reviews: PASS — verified by plan review, execution report, and audit

## PR Publishing Instructions

### Base branch
- Target: `origin/main`
- Ensure `git fetch origin main` before creating PR (local main may be stale)

### PR Description
Include the following in the PR body:
1. Summary: Automatic direnv whitelist via install.sh (~/.vibe → ~/.config/direnv/direnv.toml)
2. Changes: scripts/install.sh (+37 lines), tests (+198 lines)
3. Deviation note: TOML uses append-only strategy (multiple [whitelist] sections are valid TOML)
4. Pre-existing: 2 bats test failures unrelated to this change (fixture issue in test 2, 3)
5. Reference: Closes #3240

### PR Title
feat(install): add direnv whitelist for ~/.vibe directory

## Post-Creation
- After PR creation, `state/merge-ready` → `state/handoff` (triggered by executor)
- Manager will review PR and transition to `state/done`

## Do NOT
- Modify any files beyond the existing commit 5320a060
- Add lib/init.sh changes (confirmed out of scope)
- Remove scripts/init.sh fallback (out of scope)