#!/usr/bin/env bash
# Vibe Center 2.0 - Development Worktree Setup Script
# Automatically run by `vibe flow start` after creating a new worktree.

set -e

# --- Help ---
_usage() {
    echo -e "\n\033[1;36m🔧 Vibe Center - Development Worktree Setup Script\033[0m"
    echo ""
    echo "此脚本负责当前工作树 (Worktree) 的环境初始化，通常由 ${CYAN:-}vibe flow start${NC:-} 自动调用："
    echo "  1. 依赖注入：根据白名单配置安装项目所需的 Agents & Skills"
    echo "  2. 认知同步：初始化 OpenAPI 规范与对应的 Gate 产物"
    echo "  3. 物理挂载：建立本地 Skill 到 Agent 目录的符号链接"
    echo "  4. 任务迁移：将待处理任务同步至当前工作树的 docs/tasks 目录下"
    echo ""
    echo "Usage: ${CYAN:-}scripts/init.sh${NC:-} [options]"
    echo ""
    echo "Options:"
    echo "  -h, --help    显示此帮助信息"
    echo ""
    exit 0
}

for arg in "$@"; do
    case "$arg" in
        -h|--help) _usage ;;
    esac
done

if [[ -f "config/v3/skills.json" ]]; then
  VIBE_SKILLS_CONFIG="config/v3/skills.json"
elif [[ -f "config/skills.json" ]]; then
  VIBE_SKILLS_CONFIG="config/skills.json"
else
  VIBE_SKILLS_CONFIG="${HOME}/.vibe/skills.json"
fi

# --- Helper Functions ---
_symlink_files() {
  local source_pattern="$1"
  local target_dir="$2"
  local name_transform="${3:-identity}"  # Optional: function to transform filename
  local file_type="${4:-file}"            # Optional: 'file' or 'dir'

  mkdir -p "$target_dir"

  for item in $source_pattern; do
    if [ "$file_type" = "dir" ]; then
      [ -d "$item" ] || continue
      item="${item%/}"
    else
      [ -f "$item" ] || continue
    fi

    local name=$(basename "$item")
    if [ "$name_transform" = "add_prompt_suffix" ]; then
      name="${name%.md}.prompt.md"
    fi

    ln -sfn "../../$item" "$target_dir/$name"
  done
}

echo -e "\n\033[1;36m🔧 Setting up Vibe Center development environment...\033[0m"
echo "ℹ️  此脚本可重复运行；重复执行会复用已存在的初始化结果。"

# ── 0.5 Ensure uv CLI is discoverable ─────────────────────────────────────
if ! command -v uv &> /dev/null; then
  if [[ -x "$HOME/.local/bin/uv" ]]; then
    export PATH="$HOME/.local/bin:$PATH"
    echo "✅ uv detected at ~/.local/bin/uv"
  else
    echo -e "\033[1;33m⚠️  Warning: uv CLI not found in PATH\033[0m"
    echo "   Please run: scripts/install.sh (it bootstraps uv to ~/.local/bin)"
  fi
fi

# ── 0. Check UV_PROJECT_ENVIRONMENT ───────────────────────────────────────
# Verify that UV_PROJECT_ENVIRONMENT is set and points to global venv
if [[ -z "$UV_PROJECT_ENVIRONMENT" ]]; then
  echo -e "\033[1;33m⚠️  Warning: UV_PROJECT_ENVIRONMENT is not set\033[0m"
  echo "   Vibe Center uses a shared virtual environment at: ~/.venvs/vibe-center"
  echo ""
  echo "   Please add the following to your shell config (~/.zshrc or ~/.bashrc):"
  echo "   export UV_PROJECT_ENVIRONMENT=\"\$HOME/.venvs/vibe-center\""
  echo ""
  echo "   Or run: scripts/install.sh to set it up automatically"
elif [[ ! -d "$UV_PROJECT_ENVIRONMENT" ]]; then
  echo -e "\033[1;33m⚠️  Warning: UV_PROJECT_ENVIRONMENT directory does not exist: $UV_PROJECT_ENVIRONMENT\033[0m"
  echo "   Please create it with: uv venv $UV_PROJECT_ENVIRONMENT"
  echo "   Or run: scripts/install.sh to set it up automatically"
else
  echo "✅ UV_PROJECT_ENVIRONMENT is set: $UV_PROJECT_ENVIRONMENT"
fi

# ── 1. Install approved third-party skills from ~/.vibe/skills.json ──────────
# IMPORTANT: Skills installation should NOT be blocked by openspec/pre-commit issues
if [ -f "$VIBE_SKILLS_CONFIG" ] && command -v jq &> /dev/null; then
  echo "📦 Installing approved third-party skills from ~/.vibe/skills.json..."

  global_agents=$(jq -r '.global.agents // [] | join(" ")' "$VIBE_SKILLS_CONFIG")
  jq -c '.global.packages[]?' "$VIBE_SKILLS_CONFIG" | while read -r pkg; do
    source=$(echo "$pkg" | jq -r '.source')
    skills=$(echo "$pkg" | jq -r '.skills | join(" ")')
    echo "  → $source (global): $skills"
    # shellcheck disable=SC2086
    npx skills add "$source" -g --agent $global_agents --skill $skills -y
  done

  project_agents=$(jq -r '.project.agents // [] | join(" ")' "$VIBE_SKILLS_CONFIG")
  jq -c '.project.packages[]?' "$VIBE_SKILLS_CONFIG" | while read -r pkg; do
    source=$(echo "$pkg" | jq -r '.source')
    skills=$(echo "$pkg" | jq -r '.skills | join(" ")')
    echo "  → $source (project): $skills"
    # shellcheck disable=SC2086
    npx skills add "$source" --agent $project_agents --skill $skills -y
  done
else
  # Fallback: install superpowers for current supported non-Claude agents
  echo "📦 Installing Superpowers (fallback)..."
  npx skills add obra/superpowers -g --agent codex gemini-cli opencode github-copilot qoder codebuddy trae-cn -y
fi
echo "✅ Skills installation complete"

# ── 2. Symlink local project skills to agent directories ─────────────────────
# IMPORTANT: Symlinks should NOT be blocked by openspec/pre-commit issues
echo "🔗 Creating symlinks for local skills..."

# Link skills/vibe-* (project-owned skills)
_symlink_files "skills/vibe-*/" ".agent/skills" "identity" "dir"
_symlink_files "skills/vibe-*/" ".claude/skills" "identity" "dir"
_symlink_files "skills/vibe-*/" ".codex/skills" "identity" "dir"
_symlink_files "skills/vibe-*/" ".gemini/skills" "identity" "dir"
_symlink_files "skills/vibe-*/" ".copilot/skills" "identity" "dir"
_symlink_files "skills/vibe-*/" ".opencode/skills" "identity" "dir"
_symlink_files "skills/vibe-*/" ".qoder/skills" "identity" "dir"
_symlink_files "skills/vibe-*/" ".codebuddy/skills" "identity" "dir"

#  Symlink workflows
echo "🔗 Creating symlinks for workflows..."
_symlink_files ".agent/workflows/vibe:*.md" ".claude/commands" "identity" "file"

echo "✅ Symlinks complete"

# ── 3. Initialize OpenSpec (Optional, non-blocking) ────────────────────────────
echo "📦 Initializing OpenSpec (optional)..."
if [[ -d "openspec/specs" || -f "openspec/config.yaml" ]]; then
  echo "✅ OpenSpec already initialized"
elif command -v openspec &> /dev/null; then
  if openspec init --tools claude,codex,opencode,qoder,codebuddy,trae; then
    echo "✅ OpenSpec initialized"
  else
    echo -e "\033[1;33m⚠️  Warning: openspec init failed. Continuing (non-blocking).\033[0m"
    echo "   Run 'vibe doctor' to check optional tools status"
  fi
else
  echo -e "\033[1;33m⚠️  Warning: 'openspec' not found. Skipping (non-blocking).\033[0m"
  echo "   Install via: pnpm add -g @openspec/tools"
  echo "   Run 'vibe doctor' to check optional tools status"
fi

echo "✅ Environment setup complete!"

# ── 5. Install git hooks (pre-commit, optional, non-blocking) ─────────────────
echo "🪝 Installing git hooks (optional)..."
if command -v pre-commit &> /dev/null; then
  if pre-commit install && pre-commit install --hook-type pre-push; then
    echo "✅ Pre-commit and pre-push hooks installed"
  else
    echo -e "\033[1;33m⚠️  Warning: pre-commit hook installation failed. Continuing (non-blocking).\033[0m"
    echo "   Run 'vibe doctor' to check optional tools status"
  fi
else
  echo -e "\033[1;33m⚠️  Warning: 'pre-commit' not found. Skipping (non-blocking).\033[0m"
  echo "   Install via: uv pip install pre-commit"
  echo "   Then run: pre-commit install && pre-commit install --hook-type pre-push"
  echo "   Run 'vibe doctor' to check optional tools status"
fi

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

      if [[ -n "$task_id" && "$task_id" =~ ^[A-Za-z0-9._-]+$ ]]; then
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
      elif [[ -n "$task_id" ]]; then
        echo "⚠️  Skip pending task with unsafe task_id: $task_id"
      fi
    fi
  fi
fi
