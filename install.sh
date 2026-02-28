#!/usr/bin/env bash
# Vibe Center 2.0 - Development Worktree Setup Script
# Automatically run by `vibe flow start` after creating a new worktree.

set -e

VIBE_SKILLS_CONFIG="${HOME}/.vibe/skills.json"

echo -e "\n\033[1;36m🔧 Setting up Vibe Center development environment...\033[0m"

# ── 1. Install approved skills from ~/.vibe/skills.json ──────────────────────
if [ -f "$VIBE_SKILLS_CONFIG" ] && command -v jq &> /dev/null; then
  echo "📦 Installing approved skills from ~/.vibe/skills.json..."

  # Project-level skills
  agents=$(jq -r '.project.agents | join(" ")' "$VIBE_SKILLS_CONFIG")
  jq -c '.project.packages[]' "$VIBE_SKILLS_CONFIG" | while read -r pkg; do
    source=$(echo "$pkg" | jq -r '.source')
    skills=$(echo "$pkg" | jq -r '.skills | join(" ")')
    echo "  → $source (project): $skills"
    # shellcheck disable=SC2086
    npx skills add "$source" --agent $agents --skill $skills -y 2>/dev/null || true
  done
else
  # Fallback: install full superpowers if no config or jq not available
  echo "📦 Installing Superpowers (fallback)..."
  npx skills add obra/superpowers -y --agent antigravity trae
fi

# ── 2. Initialize OpenSpec ────────────────────────────────────────────────────
echo "📦 Initializing OpenSpec..."
if command -v openspec &> /dev/null; then
  openspec init --tools antigravity,claude,trae
else
  echo -e "\033[1;33m⚠️  Warning: 'openspec' not found. Skipping.\033[0m"
  echo "   Install via: pnpm add -g @openspec/tools"
fi

# ── 3. Symlink local project skills to agent directories ─────────────────────
echo "🔗 Creating symlinks for local skills..."
mkdir -p .agent/skills .trae/skills .claude/skills

# Link skills/vibe-* (project-owned skills)
for skill in skills/vibe-*/; do
  [ -d "$skill" ] || continue
  skill="${skill%/}"
  name=$(basename "$skill")
  ln -sfn "../../$skill" ".agent/skills/$name"
  ln -sfn "../../$skill" ".trae/skills/$name"
  ln -sfn "../../$skill" ".claude/skills/$name"
done

# Link .github/skills/openspec-* (OpenSpec skills)
for skill in .github/skills/openspec-*/; do
  [ -d "$skill" ] || continue
  skill="${skill%/}"
  name=$(basename "$skill")
  ln -sfn "../../$skill" ".agent/skills/$name"
  ln -sfn "../../$skill" ".trae/skills/$name"
  ln -sfn "../../$skill" ".claude/skills/$name"
done

echo "✅ Environment setup complete!"
