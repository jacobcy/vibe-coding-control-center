#!/usr/bin/env zsh
# Migrate Vibe Center to v2.0 - Architecture Audit Implementation
# Date: 2026-02-25
# Rationale: docs/audits/2026-02-25-architecture-audit.md

set -e

readonly REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
readonly RED=$'\033[0;31m'
readonly GREEN=$'\033[0;32m'
readonly YELLOW=$'\033[1;33m'
readonly CYAN=$'\033[0;36m'
readonly BOLD=$'\033[1m'
readonly NC=$'\033[0m'

log_step()    { echo "${CYAN}▶ $1${NC}"; }
log_success() { echo "${GREEN}✓ $1${NC}"; }
log_warn()    { echo "${YELLOW}⚠ $1${NC}"; }
log_error()   { echo "${RED}✗ $1${NC}" >&2; exit 1; }

confirm() {
    local prompt="$1"
    echo -n "${YELLOW}? $prompt [y/N]: ${NC}"
    read -r response
    [[ "$response" =~ ^[yY](es)?$ ]] || { log_warn "Aborted by user"; exit 0; }
}

# ── Preflight Checks ──────────────────────────────────
cd "$REPO_ROOT" || log_error "Cannot cd to repo root"

log_step "Preflight checks..."

# Check we're in the right repo
[[ -d "v2" ]] || log_error "v2/ directory not found. Are you in the right repo?"
[[ -f "docs/audits/2026-02-25-architecture-audit.md" ]] || \
    log_error "Audit report not found. Run from repo root."

# Check git status
if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
    log_warn "You have uncommitted changes:"
    git status --short
    confirm "Continue anyway?"
fi

# Check current branch
current_branch="$(git branch --show-current 2>/dev/null)"
if [[ "$current_branch" != "main" ]]; then
    log_warn "Currently on branch: $current_branch (not main)"
    confirm "Switch to main and continue?"
    git checkout main || log_error "Failed to checkout main"
fi

log_success "Preflight checks passed"
echo ""

# ── Show Migration Plan ───────────────────────────────
echo "${BOLD}Migration Plan:${NC}"
echo "  1. Archive v1 → ${CYAN}archive/v1-legacy${NC} branch"
echo "  2. Copy v2/ → root directory"
echo "  3. Remove v2/ subdirectory"
echo "  4. Commit as v2.0.0 breaking change"
echo "  5. Create v2.0.0 tag"
echo "  6. Push to origin (--force-with-lease)"
echo ""

# Show code reduction stats
v1_loc=$(find lib/ bin/ -name '*.sh' -o -name 'vibe*' 2>/dev/null | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}')
v2_loc=$(find v2/lib/ v2/bin/ -name '*.sh' -o -name 'vibe' 2>/dev/null | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}')
reduction=$((v1_loc - v2_loc))
reduction_pct=$((reduction * 100 / v1_loc))

echo "${BOLD}Code Reduction:${NC}"
echo "  Before: lib/+bin/ = ${RED}${v1_loc}${NC} lines"
echo "  After:  lib/+bin/ = ${GREEN}${v2_loc}${NC} lines"
echo "  Delta:  ${YELLOW}-${reduction}${NC} lines (${BOLD}-${reduction_pct}%${NC})"
echo ""

confirm "Proceed with migration?"

# ── Step 1: Archive v1 ────────────────────────────────
log_step "Step 1: Archiving v1 to archive/v1-legacy branch..."

# Check if archive branch already exists
if git show-ref --verify --quiet refs/heads/archive/v1-legacy; then
    log_warn "Branch archive/v1-legacy already exists"
    confirm "Delete and recreate?"
    git branch -D archive/v1-legacy
fi

git branch archive/v1-legacy main
log_success "Created archive/v1-legacy branch"

# Push archive branch
if git ls-remote --heads origin archive/v1-legacy | grep -q archive/v1-legacy; then
    log_warn "Remote archive/v1-legacy already exists"
    confirm "Force push?"
    git push origin archive/v1-legacy --force
else
    git push origin archive/v1-legacy
fi
log_success "Pushed archive/v1-legacy to origin"
echo ""

# ── Step 2: Backup (safety net) ───────────────────────
log_step "Step 2: Creating local backup..."
backup_dir="../vibe-center-v1-backup-$(date +%Y%m%d-%H%M%S)"
cp -r . "$backup_dir"
log_success "Backup created: $backup_dir"
echo ""

# ── Step 3: Copy v2 to root ───────────────────────────
log_step "Step 3: Copying v2/ contents to root..."

# Remove old v1 files (keep .git, v2/, docs/audits/)
log_step "  Removing v1 files..."
git rm -rf bin/ lib/ config/ scripts/ install/ tests/ 2>/dev/null || true
rm -rf openspec/ .openspec/ temp/ 2>/dev/null || true

# Copy v2 files to root
log_step "  Copying v2 files to root..."
rsync -av v2/ . \
    --exclude=.git \
    --exclude=.DS_Store \
    --exclude='*.swp'

log_success "v2 content copied to root"
echo ""

# ── Step 4: Clean up v2 directory ─────────────────────
log_step "Step 4: Removing v2/ directory..."
git rm -rf v2/
rm -rf v2/
log_success "v2/ directory removed"
echo ""

# ── Step 5: Update VERSION ────────────────────────────
log_step "Step 5: Updating VERSION to 2.0.0..."
echo "2.0.0" > VERSION
git add VERSION
log_success "VERSION updated"
echo ""

# ── Step 6: Commit ────────────────────────────────────
log_step "Step 6: Creating commit..."

git add -A

cat > /tmp/v2-commit-msg.txt <<'EOF'
feat: v2.0 rebuild - 92% code reduction following architecture audit

## Breaking Changes
- Complete rebuild based on 2026-02-25 architecture audit
- Code reduced from 8,161 to 644 lines (92% reduction)
- Removed over-engineering: NLP router, circuit breaker, i18n, cache system
- Established HARD RULES for scope control (LOC ceiling, single file limit)

## Migration Guide
- v1 code archived in `archive/v1-legacy` branch
- v2 is a minimalist rewrite, NOT backward compatible
- See docs/audits/2026-02-25-architecture-audit.md for full rationale

## What Changed
### Deleted Modules (dead code / over-engineering)
- lib/error_handling.sh (circuit breaker pattern)
- lib/cache.sh (TTL cache system)
- lib/email_validation.sh
- lib/i18n.sh (4-language i18n framework)
- lib/chat_router.sh (NLP intent routing)
- lib/testing.sh (custom test framework)
- lib/config_loader.sh (duplicate of config.sh)
- lib/config_migration.sh

### Core Modules (preserved & simplified)
- lib/utils.sh: 977 → 74 lines (logging, validation, command helpers)
- lib/config.sh: 226 → 40 lines (VIBE_ROOT detection, keys loading)
- lib/flow.sh: 747 → 168 lines (dev workflow lifecycle)
- lib/keys.sh: 80 lines (NEW, extracted from keys_manager.sh)
- lib/check.sh: 82 lines (NEW, environment diagnostics)
- lib/equip.sh: 124 lines (NEW, tool installation)

### Governance (NEW)
- CLAUDE.md: Added 7 HARD RULES (LOC ceiling, scope gate, etc.)
- SOUL.md: Added "Cognition First" philosophy
- .agent/: Agent workspace structure

## LOC Diff
Before: lib/+bin/ = 8,161 lines (v1)
After:  lib/+bin/ = 644 lines (v2)
Delta:  -7,517 lines (-92%)

Total files: 195 → 19 (-90%)
Functions: 205 → 34 (-83%)
Modules: 21 → 6 (-71%)

## References
- Architecture Audit: docs/audits/2026-02-25-architecture-audit.md
- Constitution: SOUL.md §2 "Cognition First"
- v1 Archive: archive/v1-legacy branch

BREAKING CHANGE: Complete rebuild, no backward compatibility with v1.
EOF

git commit -F /tmp/v2-commit-msg.txt
rm /tmp/v2-commit-msg.txt
log_success "Committed v2.0.0"
echo ""

# ── Step 7: Tag ───────────────────────────────────────
log_step "Step 7: Creating v2.0.0 tag..."
if git tag -l | grep -q '^v2.0.0$'; then
    log_warn "Tag v2.0.0 already exists"
    confirm "Delete and recreate?"
    git tag -d v2.0.0
fi

git tag -a v2.0.0 -m "Vibe Center 2.0 - Cognition First Rebuild

92% code reduction (8,161 → 644 lines)
Rationale: docs/audits/2026-02-25-architecture-audit.md"

log_success "Created tag v2.0.0"
echo ""

# ── Step 8: Push ──────────────────────────────────────
log_step "Step 8: Pushing to origin..."

echo ""
echo "${BOLD}${YELLOW}⚠ WARNING: This will force-push to main branch!${NC}"
echo "   Remote commits not in local history will be lost."
echo "   v1 code is preserved in archive/v1-legacy branch."
echo ""

confirm "Force push to origin/main?"

git push origin main --force-with-lease || \
    log_error "Push failed. Check git status and try manually."
git push origin v2.0.0 || log_warn "Tag push failed (may already exist remotely)"

log_success "Pushed to origin"
echo ""

# ── Done ──────────────────────────────────────────────
echo "${BOLD}${GREEN}✓ Migration Complete!${NC}"
echo ""
echo "Summary:"
echo "  • v1 archived: ${CYAN}archive/v1-legacy${NC} branch"
echo "  • v2 deployed: ${CYAN}main${NC} branch (${GREEN}v2.0.0${NC})"
echo "  • Backup: ${CYAN}${backup_dir}${NC}"
echo ""
echo "Next steps:"
echo "  1. Verify deployment: ${CYAN}git log --oneline -3${NC}"
echo "  2. Test CLI: ${CYAN}./bin/vibe check${NC}"
echo "  3. Update README if needed"
echo "  4. Remove backup after verification: ${CYAN}rm -rf ${backup_dir}${NC}"
echo ""
echo "Audit report: ${CYAN}docs/audits/2026-02-25-architecture-audit.md${NC}"
