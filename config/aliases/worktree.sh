#!/usr/bin/env zsh
# Worktree management commands

alias wtls='git worktree list'

# Jump to a worktree by name
wt() {
  local target="$1"
  [[ -z "$target" ]] && { git worktree list; return; }
  local wt_path
  wt_path="$(git worktree list --porcelain 2>/dev/null |
    awk -v name="$target" '/^worktree /{
      path=substr($0,10); b=path; sub(/.*\//,"",b)
      if(b==name||path==name){print path; exit}
    }')"
  if [[ -n "$wt_path" && -d "$wt_path" ]]; then
    cd "$wt_path" || return
    [[ -n "$TMUX" ]] && tmux rename-window "${target:t}"
  else
    echo "❌ Worktree not found: $target"; git worktree list 2>/dev/null | sed 's/^/   /'; return 1
  fi
}

# Create new worktree: wtnew <branch> [agent] [base]
wtnew() {
  local git_cmd; git_cmd="$(vibe_find_cmd git)" || { vibe_die "git not found"; return 1; }
  local branch="$1" agent="${2:-claude}" base="${3:-main}"
  [[ -z "$branch" ]] && vibe_die "usage: wtnew <branch> [agent=claude|opencode|codex] [base=main]"

  local repo_root
  repo_root="$($git_cmd rev-parse --show-toplevel 2>/dev/null)" || vibe_die "Not in a git repo"

  # Must be on main/master
  local cur_br; cur_br="$($git_cmd -C "$repo_root" branch --show-current 2>/dev/null)"
  if [[ "$cur_br" != "main" && "$cur_br" != "master" ]]; then
    echo "⚠️  On '$cur_br', not main. Switch first: cd $repo_root && git checkout main"; return 1
  fi

  local dir="wt-${agent}-${branch}"
  local path="${repo_root:h}/$dir"

  $git_cmd -C "$repo_root" fetch -p >/dev/null 2>&1 || true
  $git_cmd -C "$repo_root" show-ref --verify --quiet "refs/heads/$branch" || \
    $git_cmd -C "$repo_root" branch "$branch" "$base" 2>/dev/null || true

  if [[ -e "$path" ]]; then
    echo "ℹ️  Worktree exists: $dir"
  else
    $git_cmd -C "$repo_root" worktree add "$path" "$branch" || return 1
    echo "✅ Created worktree: $dir -> $branch (base: $base)"
  fi

  # Set agent identity
  local aname="Agent-${(C)agent}" aemail="agent-${agent}@vibecoding.ai"
  $git_cmd -C "$path" config user.name "$aname"
  $git_cmd -C "$path" config user.email "$aemail"
  echo "👤 Identity: $aname <$aemail>"
  cd "$path" || return
}

# Remove worktree(s): wtrm <name|path|all>
wtrm() {
  local git_cmd; git_cmd="$(vibe_find_cmd git)" || { vibe_die "git not found"; return 1; }
  local arg="$1"; [[ -z "$arg" ]] && vibe_die "usage: wtrm <wt-dir|path|all>"

  local main_dir; main_dir="$($git_cmd rev-parse --show-toplevel 2>/dev/null)" || { vibe_die "Not in git repo"; return 1; }

  _wtrm_one() {
    local p="$1" label="${1##*/}"
    [[ "$p" == "$main_dir" ]] && { echo "⚠️  Cannot remove main worktree"; return 1; }
    
    local branch_name=""
    if [[ -d "$p" ]]; then
      branch_name=$($git_cmd -C "$p" rev-parse --abbrev-ref HEAD 2>/dev/null)
    fi
    if [[ -z "$branch_name" ]]; then
      branch_name=$($git_cmd -C "$main_dir" worktree list --porcelain | awk -v path="$p" '
        /^worktree / { if ($2 == path) found=1; else found=0 }
        /^branch / && found { sub("refs/heads/", "", $2); print $2; exit }
      ')
    fi

    if $git_cmd -C "$main_dir" worktree remove --force "$p" 2>/dev/null; then
      echo "✅ Removed: $label"
      
      if [[ -n "$branch_name" && "$branch_name" != "main" && "$branch_name" != "master" ]]; then
        if $git_cmd -C "$main_dir" branch -D "$branch_name" >/dev/null 2>&1; then
           echo "🗑️  Deleted local branch: $branch_name"
        fi
        if $git_cmd -C "$main_dir" ls-remote --exit-code --heads origin "$branch_name" >/dev/null 2>&1; then
           echo -n "❓ Delete remote branch origin/$branch_name? [y/N] "
           local response
           read -r response
           if [[ "$response" =~ ^[yY]$ ]]; then
              if $git_cmd -C "$main_dir" push origin --delete "$branch_name"; then
                 echo "🗑️  Deleted remote branch: origin/$branch_name"
              fi
           else
              echo "ℹ️  Kept remote branch"
           fi
        fi
      fi
    elif [[ -d "$p" ]]; then
      command rm -rf "$p"; echo "🗑️  Deleted orphan: $label"
    else
      echo "⚠️  Not found: $p"
    fi
  }

  if [[ "$arg" == "all" ]]; then
    local -a paths=()
    while IFS= read -r wp; do
      [[ "$wp" == "$main_dir" ]] && continue
      [[ "${wp##*/}" == wt-* ]] && paths+=("$wp")
    done < <($git_cmd -C "$main_dir" worktree list --porcelain | awk '/^worktree /{print $2}')
    [[ ${#paths[@]} -eq 0 ]] && { echo "ℹ️  No wt-* worktrees"; return 0; }
    echo "🗑️  Removing ${#paths[@]} worktree(s)..."
    for wp in "${paths[@]}"; do _wtrm_one "$wp"; done
  else
    local path
    [[ "$arg" == /* ]] && path="$arg" || path="${main_dir:h}/$arg"
    [[ "$path" =~ /wt- ]] || { echo "⚠️  Name must contain 'wt-': $arg"; return 1; }
    _wtrm_one "$path"
  fi
  $git_cmd -C "$main_dir" worktree prune >/dev/null 2>&1 || true
}

# Re-sync git identity in current worktree
wtinit() {
  local agent="${1:-claude}"
  [[ -d ".git" || -f ".git" ]] || vibe_die "Not in a git repo/worktree"
  local aname="Agent-${(C)agent}" aemail="agent-${agent}@vibecoding.ai"
  git config user.name "$aname"; git config user.email "$aemail"
  echo "✅ Identity: $aname <$aemail>"
}

# Refresh worktree state
wtrenew() {
  local wt="${PWD##*/}"; echo "🔄 Refreshing: $wt"
  local name; name="$(git config user.name 2>/dev/null)"
  [[ -z "$name" ]] && { wtinit claude; return; }
  echo "✅ Identity OK: $name <$(git config user.email 2>/dev/null)>"
}

# Set up tmux workspace for a worktree
vup() {
  vibe_require tmux git || return 1
  local wt_dir="${1:-main}" agent="${2:-claude}" editor="${3:-${EDITOR:-vim}}"

  # Auto-detect worktree name if not specified
  if [[ -z "$1" ]] && command -v git >/dev/null 2>&1; then
    local gr; gr="$(git rev-parse --show-toplevel 2>/dev/null)"
    [[ -n "$gr" ]] && { local dn="${gr##*/}"; [[ "$dn" == wt-* ]] && wt_dir="$dn"; }
  fi

  # Resolve path
  local dir_path
  if [[ "$wt_dir" == "main" ]]; then dir_path="$VIBE_MAIN"
  elif [[ "$wt_dir" == /* ]]; then dir_path="$wt_dir"
  else
    local rr; rr="$(git rev-parse --show-toplevel 2>/dev/null)"
    dir_path="${rr:+${rr:h}/$wt_dir}"
    [[ -z "$dir_path" ]] && dir_path="$VIBE_REPO/$wt_dir"
  fi
  [[ -d "$dir_path" ]] || vibe_die "Not found: $dir_path"

  vibe_tmux_ensure || return 1
  vibe_tmux_win "${wt_dir}-edit" "$dir_path" "$editor" || return 1

  # Agent window
  case "$agent" in
    opencode) vibe_require opencode; vibe_tmux_win "${wt_dir}-agent" "$dir_path" "opencode" ;;
    codex)    vibe_require codex;    vibe_tmux_win "${wt_dir}-agent" "$dir_path" "codex --yes" ;;
    *)        vibe_require claude;   vibe_tmux_win "${wt_dir}-agent" "$dir_path" "claude --dangerously-skip-permissions --continue" ;;
  esac || return 1

  vibe_tmux_win "${wt_dir}-tests" "$dir_path" || return 1
  vibe_tmux_win "${wt_dir}-logs"  "$dir_path" || return 1
  vibe_has lazygit && vibe_tmux_win "${wt_dir}-git" "$dir_path" "lazygit" \
                   || vibe_tmux_win "${wt_dir}-git" "$dir_path"
  echo "✅ Workspace ready: $wt_dir (agent: $agent)"
}

# One-shot: wtnew + vup
vnew() {
  local branch="$1" agent="${2:-claude}" base="${3:-main}"
  [[ -z "$branch" ]] && vibe_die "usage: vnew <branch> [agent] [base]"
  wtnew "$branch" "$agent" "$base" || return 1
  vup "wt-${agent}-$branch" "$agent" || return 1
  echo "✅ Ready. Review in lazygit window."
}
