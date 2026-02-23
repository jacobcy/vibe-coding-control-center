#!/usr/bin/env zsh
# ======================================================
# Worktree 命令
# ======================================================

# 列出 worktrees
alias wtls='git worktree list'

# 跳转到 worktree 目录
wt() {
  local target="$1"
  if [[ -z "$target" ]]; then
    git -C "$VIBE_REPO" worktree list
    return
  fi
  cd "$VIBE_REPO/$target" || return
  [[ -n "$TMUX" ]] && tmux rename-window "$target"
}

# 创建新 worktree（修复路径计算）
# usage: wtnew <branch-name> [agent=claude|opencode|codex] [base-branch=main]
wtnew() {
  vibe_load_context
  # Find git command - check PATH and common locations
  local git_cmd
  git_cmd="$(vibe_find_cmd git)" || {
    vibe_die "git command not found. Please ensure git is installed and in your PATH."
    return 1
  }

  local branch="$1"
  local agent="${2:-claude}"
  local base="${3:-main}"

  [[ -z "$branch" ]] && vibe_die "usage: wtnew <branch-name> [agent=claude|opencode|codex] [base-branch=main]"

  # 使用 git rev-parse --show-toplevel 获取准确的仓库根
  local current_dir="$(pwd)"
  local repo_root

  if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    repo_root="$(git rev-parse --show-toplevel 2>/dev/null)"
  else
    repo_root="${current_dir}"
    # 如果当前目录不是 git 仓库，尝试向上查找
    while [[ "$repo_root" != "/" && ! -d "$repo_root/.git" && ! -f "$repo_root/.git" ]]; do
      repo_root="$(dirname "$repo_root")"
    done
    if [[ "$repo_root" == "/" ]]; then
      vibe_die "Could not find git repository root"
      return 1
    fi
  fi

  # 检查我们是否在 main 分支上
  local current_branch
  current_branch="$(git -C "$repo_root" branch --show-current 2>/dev/null)"

  if [[ "$current_branch" != "main" && "$current_branch" != "master" ]]; then
    echo "⚠️  You are on branch '$current_branch', not main/master"
    echo "   Current directory: $repo_root"
    echo ""
    echo "💡 Please switch to main/master branch first:"
    echo "   cd $repo_root"
    echo "   git checkout main"
    echo "   wtnew $branch $agent $base"
    return 1
  fi

  local prefix="wt-${agent}-"
  local dir="${prefix}${branch}"
  local path

  # 修复路径计算：使用 repo_root 的父目录放置 worktree
  # 如果 repo_root 本身就是仓库根，则在其同级目录创建 worktree
  local parent_dir="$(dirname "$repo_root")"
  path="$parent_dir/$dir"

  # Create branch from base in main repo context
  $git_cmd -C "$repo_root" fetch -p >/dev/null 2>&1 || true
  $git_cmd -C "$repo_root" show-ref --verify --quiet "refs/heads/$branch" || \
    $git_cmd -C "$repo_root" branch "$branch" "$base" 2>/dev/null || true

  # Add worktree
  if [[ -e "$path" ]]; then
    echo "ℹ️  Worktree dir already exists: $dir"
  else
    $git_cmd -C "$repo_root" worktree add "$path" "$branch" || return 1
    echo "✅ Created worktree: $dir -> branch $branch (base: $base)"
  fi

  # Set agent identity in worktree
  local agent_name="Agent-${(C)agent}"
  local agent_email="agent-${agent}@vibecoding.ai"

  $git_cmd -C "$path" config user.name "$agent_name"
  $git_cmd -C "$path" config user.email "$agent_email"
  echo "👤 Git identity set: $agent_name <$agent_email>"

  cd "$path" || return
}

# 删除 worktree
wtrm() {
  local git_cmd
  git_cmd="$(vibe_find_cmd git)" || { vibe_die "git not found"; return 1; }

  local arg="$1"
  [[ -z "$arg" ]] && vibe_die "usage: wtrm <wt-dir|absolute-path|all>"

  # ====== 安全修复: 不再使用父目录计算 ======
  # 直接使用 git worktree list 获取准确的 worktree 路径
  local main_dir
  main_dir="$($git_cmd -C "$PWD" rev-parse --show-toplevel 2>/dev/null)"

  if [[ -z "$main_dir" ]]; then
    vibe_die "Not in a git repository"
    return 1
  fi

  # 验证 main_dir 是有效的 git 目录
  if [[ ! -d "$main_dir/.git" && ! -f "$main_dir/.git" ]]; then
    vibe_die "Not a valid git repository: $main_dir"
    return 1
  fi

  # Helper function to remove a single worktree
  _wtrm_one() {
    local p="$1"
    local label="${p##*/}"

    # 安全检查：确保不删除主目录
    if [[ "$p" == "$main_dir" ]]; then
      echo "⚠️  Cannot remove main worktree: $p"
      return 1
    fi

    if $git_cmd -C "$main_dir" worktree remove --force "$p" 2>/dev/null; then
      echo "✅ Removed worktree: $label"
    elif [[ -d "$p" ]]; then
      local rm_cmd
      if command -v rm >/dev/null 2>&1; then
        rm_cmd="rm"
      elif [[ -x "/bin/rm" ]]; then
        rm_cmd="/bin/rm"
      elif [[ -x "/usr/bin/rm" ]]; then
        rm_cmd="/usr/bin/rm"
      else
        echo "❌ rm command not found, cannot delete: $label" >&2
        return 1
      fi
      $rm_cmd -rf "$p"
      echo "🗑️  Deleted orphaned directory: $label"
    else
      echo "⚠️  Not found: $p"
    fi
  }

  if [[ "$arg" == "all" ]]; then
    local -a wt_paths=()
    while IFS= read -r wt_path; do
      # 跳过主 worktree
      [[ "$wt_path" == "$main_dir" ]] && continue
      # 只删除 wt-* 开头的 worktree
      [[ "${wt_path##*/}" == wt-* ]] && wt_paths+=("$wt_path")
    done < <($git_cmd -C "$main_dir" worktree list --porcelain | awk '/^worktree /{print $2}')

    if [[ ${#wt_paths[@]} -eq 0 ]]; then
      echo "ℹ️  No wt-* worktrees to remove"
      return 0
    fi

    echo "🗑️  Removing ${#wt_paths[@]} worktree(s)..."
    for wt_path in "${wt_paths[@]}"; do
      _wtrm_one "$wt_path"
    done
  else
    # 解析路径：绝对路径或相对于 repo root
    local path
    if [[ "$arg" == /* ]]; then
      path="$arg"
    else
      # 修复：直接使用 repo root，不使用父目录
      local repo_root
      repo_root="$(dirname "$main_dir")"
      path="$repo_root/$arg"
    fi

    # 安全检查：确保路径在预期范围内
    if [[ ! "$path" =~ ^.+/wt- ]]; then
      echo "⚠️  Worktree name must start with 'wt-': $arg"
      echo "   Use 'wtrm all' to remove all wt-* worktrees"
      return 1
    fi

    _wtrm_one "$path"
  fi

  $git_cmd -C "$main_dir" worktree prune >/dev/null 2>&1 || true
  echo "🧹 Pruned stale worktree references"
}

# 同步 Git identity（重新初始化）
wtinit() {
  local agent="${1:-claude}"

  if [[ ! -d ".git" && ! -f ".git" ]]; then
    vibe_die "Not in a git repository or worktree."
  fi

  local agent_name="Agent-${(C)agent}"
  local agent_email="agent-${agent}@vibecoding.ai"

  git config user.name "$agent_name"
  git config user.email "$agent_email"
  echo "✅ Git identity re-synced: $agent_name <$agent_email>"
}

# 重新初始化/刷新（原 vfr）
wtrenew() {
  local wt_name="${PWD##*/}"
  echo "🔄 Refreshing worktree: $wt_name"

  # 获取当前分支并重新同步 identity
  local current_branch
  current_branch="$(git branch --show-current 2>/dev/null)"
  if [[ -n "$current_branch" ]]; then
    echo "📌 Current branch: $current_branch"
  fi

  # 重新同步 git identity
  local agent_name
  local agent_email
  agent_name="$(git config user.name 2>/dev/null)"
  agent_email="$(git config user.email 2>/dev/null)"

  if [[ -z "$agent_name" || -z "$agent_email" ]]; then
    echo "⚠️  Git identity not set, using default claude"
    wtinit claude
  else
    echo "✅ Git identity already set: $agent_name <$agent_email>"
  fi

  echo "✅ Worktree refreshed"
}

# tmux workspace（修复路径计算）
vup() {
  vibe_load_context
  vibe_require tmux git || return 1

  local wt_dir="${1:-main}"
  local agent="${2:-claude}"
  local editor_cmd="${3:-${EDITOR:-vim}}"

  # 检测是否在 worktree 中
  if [[ "$1" == "" ]] && command -v git >/dev/null 2>&1; then
    local git_root
    git_root="$(git rev-parse --show-toplevel 2>/dev/null)"
    if [[ -n "$git_root" ]]; then
      local git_dirname="${git_root##*/}"
      if [[ "$git_dirname" == wt-* ]]; then
        wt_dir="$git_dirname"
      elif [[ "$git_root" == "$VIBE_MAIN" ]]; then
        wt_dir="main"
      fi
    fi
  fi

  # 修复路径计算：使用正确的路径
  local dir_path
  if [[ "$wt_dir" == "main" ]]; then
    dir_path="$VIBE_MAIN"
  else
    # 检查是否是绝对路径
    if [[ "$wt_dir" == /* ]]; then
      dir_path="$wt_dir"
    else
      # 使用 git worktree list 获取准确的路径
      local repo_root
      repo_root="$(git rev-parse --show-toplevel 2>/dev/null)"
      if [[ -n "$repo_root" ]]; then
        local parent_dir
        parent_dir="$(dirname "$repo_root")"
        dir_path="$parent_dir/$wt_dir"
      else
        dir_path="$VIBE_REPO/$wt_dir"
      fi
    fi
  fi

  [[ -d "$dir_path" ]] || vibe_die "worktree dir not found: $dir_path"

  vibe_tmux_ensure || return 1

  local w_edit="${wt_dir}-edit"
  local w_agent="${wt_dir}-agent"
  local w_tests="${wt_dir}-tests"
  local w_logs="${wt_dir}-logs"
  local w_git="${wt_dir}-git"

  # Editor window
  vibe_tmux_win "$w_edit" "$dir_path" "$editor_cmd" || return 1

  # Agent window
  case "$agent" in
    opencode)
      vibe_require opencode || return 1
      vibe_tmux_win "$w_agent" "$dir_path" "opencode" || return 1
      ;;
    codex)
      vibe_require codex || return 1
      vibe_tmux_win "$w_agent" "$dir_path" "codex --yes" || return 1
      ;;
    *)
      vibe_require claude || return 1
      vibe_tmux_win "$w_agent" "$dir_path" "claude --dangerously-skip-permissions --continue" || return 1
      ;;
  esac

  # Tests/logs windows
  vibe_tmux_win "$w_tests" "$dir_path" || return 1
  vibe_tmux_win "$w_logs" "$dir_path" || return 1

  # lazygit window
  vibe_require lazygit || echo "⚠️  lazygit not found; '$w_git' will open a shell"
  if vibe_has lazygit; then
    vibe_tmux_win "$w_git" "$dir_path" "lazygit" || return 1
  else
    vibe_tmux_win "$w_git" "$dir_path" || return 1
  fi

  echo "✅ tmux workspace ready for: $wt_dir (agent: $agent) @ $(vibe_now)"
  echo "👉 attach with: vt"
}

# wtnew + vup 一键操作
vnew() {
  vibe_load_context
  local branch="$1"
  local agent="${2:-claude}"
  local base="${3:-main}"

  [[ -z "$branch" ]] && vibe_die "usage: vnew <branch> [agent=claude|opencode|codex] [base=main]"

  wtnew "$branch" "$agent" "$base" || return 1
  local wt_dir="wt-${agent}-$branch"
  vup "$wt_dir" "$agent" || return 1
  echo "✅ All set. Your job: review/commit in lazygit window (${wt_dir}-git)."
}
