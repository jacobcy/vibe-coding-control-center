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
    npx skills add "$source" --agent $agents --skill $skills -y
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

# ── 4. Migrate matching pending task into docs/tasks/ ────────────────────────
if command -v git &> /dev/null && command -v jq &> /dev/null; then
  current_dir="$(basename "$PWD")"
  current_path="$PWD"
  current_feature=""
  current_task_id=""
  if [[ "$current_dir" =~ ^wt-[^-]+-(.+)$ ]]; then
    current_feature="${BASH_REMATCH[1]}"
  fi

  common_dir="$(git rev-parse --git-common-dir 2>/dev/null || true)"
  pending_dir="$common_dir/vibe/pending-tasks"
  worktrees_file="$common_dir/vibe/worktrees.json"

  if [[ -f "$worktrees_file" ]]; then
    current_task_id="$(jq -r --arg worktree_path "$current_path" --arg worktree_name "$current_dir" '
      .worktrees[]? | select(.worktree_path == $worktree_path or .worktree_name == $worktree_name) | .current_task // empty
    ' "$worktrees_file" | head -n 1)"
  fi

  if [[ -d "$pending_dir" ]]; then
    pending_file=""
    while IFS= read -r candidate; do
      if jq -e --arg task_id "$current_task_id" --arg feature "$current_feature" '
        (($task_id != "") and (.task_id == $task_id))
        or (($task_id == "") and ($feature != "") and (.assigned_feature == $feature))
      ' "$candidate" >/dev/null 2>&1; then
        pending_file="$candidate"
        break
      fi
    done < <(find "$pending_dir" -maxdepth 1 -type f -name '*.json' | sort)

    if [[ -n "$pending_file" ]]; then
      task_id="$(jq -r '.task_id // empty' "$pending_file")"
      task_title="$(jq -r '.title // .assigned_feature // "Pending Task"' "$pending_file")"
      task_title_yaml="${task_title//$'\r'/ }"
      task_title_yaml="${task_title_yaml//$'\n'/ }"
      task_title_yaml="${task_title_yaml//\'/\'\'}"
      task_status="$(jq -r '.status // "todo"' "$pending_file")"
      pending_feature="$(jq -r '.assigned_feature // empty' "$pending_file")"

      if [[ -n "$task_id" ]]; then
        task_dir="docs/tasks/$task_id"
        task_readme="$task_dir/README.md"
        mkdir -p "$task_dir"

        if [[ ! -f "$task_readme" ]]; then
          cat > "$task_readme" <<EOF
---
task_id: "$task_id"
document_type: task-readme
title: '$task_title_yaml'
current_layer: "plan"
status: "$task_status"
author: "Vibe Setup Script"
created: "$(date +%F)"
last_updated: "$(date +%F)"
related_docs: []
gates:
  scope:
    status: "pending"
  spec:
    status: "pending"
  plan:
    status: "pending"
  test:
    status: "pending"
  code:
    status: "pending"
  audit:
    status: "pending"
---

# Task: $task_title

## 概述

- source: $(jq -r '.source // "pending-task"' "$pending_file")
- framework: $(jq -r '.framework // "vibe"' "$pending_file")
- assigned feature: ${pending_feature:-$current_feature}

## 当前状态

- status: $task_status
- created from pending task: $(basename "$pending_file")

## 下一步

- [ ] 进入 `/vibe-new ${pending_feature:-$current_feature}` 流程补齐 Gate 产物
EOF
          echo "📝 Migrated pending task to $task_readme"
        fi

        rm -f "$pending_file"
        echo "🧹 Cleaned pending task file: $(basename "$pending_file")"
      fi
    fi
  fi
fi
