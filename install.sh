#!/usr/bin/env bash
# Vibe Center 2.0 - Development Worktree Setup Script
# Automatically run by `vibe flow start` after creating a new worktree.

set -e

echo -e "\n\033[1;36m🔧 Setting up Vibe Center development environment...\033[0m"

echo "📦 Installing Superpowers..."
npx skills add obra/superpowers -y --agent antigravity claude-code trae

echo "📦 Initializing OpenSpec..."
if command -v openspec &> /dev/null; then
  openspec init --tools antigravity,claude,trae
else
  echo -e "\033[1;33m⚠️  Warning: 'openspec' command not found. Skipping OpenSpec initialization.\033[0m"
  echo "   Please install it globally via: pnpm add -g @openspec/tools"
fi

echo "🔗 Creating symlinks for local and OpenSpec skills..."
mkdir -p .agent/skills .trae/skills

# 1. Link local project skills
for skill in skills/vibe-*/; do
  if [ -d "$skill" ]; then
    name=$(basename "$skill")
    ln -sf "../../$skill" ".agent/skills/$name"
    ln -sf "../../$skill" ".trae/skills/$name"
  fi
done

# 2. Link OpenSpec skills
for skill in .github/skills/openspec-*/; do
  if [ -d "$skill" ]; then
    name=$(basename "$skill")
    ln -sf "../../$skill" ".agent/skills/$name"
    ln -sf "../../$skill" ".trae/skills/$name"
  fi
done

echo "✅ Environment setup complete!"
