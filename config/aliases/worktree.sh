#!/usr/bin/env zsh
# Worktree management commands

# @desc List all worktrees
# @featured
alias wtls='git worktree list'

# @desc Jump to a specific worktree by name (e.g. wt my-feat)
# @featured
wt() {
  local target="$1"
  [[ -z "$target" ]] && { git worktree list; return; }

  # Collect all accessible worktree paths
  local -a all_paths=()
  while IFS= read -r p; do [[ -d "$p" ]] && all_paths+=("$p"); done \
    < <(git worktree list --porcelain 2>/dev/null | awk '/^worktree /{print substr($0,10)}')
  [[ ${#all_paths[@]} -eq 0 ]] && { echo "❌ Not in a git repository"; return 1; }

  _wt_enter() {
    local p="$1" label="${1##*/}"
    cd "$p" || return 1
    [[ -n "$TMUX" ]] && tmux rename-window "$label"
    echo "→ $label"
  }

  # ① Exact match: full basename or absolute path
  local p b
  for p in "${all_paths[@]}"; do
    b="${p##*/}"
    [[ "$b" == "$target" || "$p" == "$target" ]] && { _wt_enter "$p"; return; }
  done

  # ② Suffix match: basename ends with "-<target>" (catches agent-feat and wt-agent-feat)
  local -a candidates=()
  for p in "${all_paths[@]}"; do
    [[ "${p##*/}" == *"-${target}" ]] && candidates+=("$p")
  done

  # ③ Substring fallback: basename contains "<target>" anywhere
  if [[ ${#candidates[@]} -eq 0 ]]; then
    for p in "${all_paths[@]}"; do
      [[ "${p##*/}" == *"${target}"* ]] && candidates+=("$p")
    done
  fi

  case ${#candidates[@]} in
    0)
      echo "❌ Worktree not found: $target"
      git worktree list 2>/dev/null | sed 's/^/   /'
      return 1 ;;
    1)
      _wt_enter "${candidates[1]}" ;;
    *)
      echo "🔍 Multiple worktrees match '${target}':"
      local i=1
      for c in "${candidates[@]}"; do
        echo "  [$i] ${c##*/}   ($c)"
        (( i++ ))
      done
      echo -n "Enter choice [1-${#candidates[@]}]: "
      local choice; read -r choice
      if [[ "$choice" =~ ^[0-9]+$ ]] && (( choice >= 1 && choice <= ${#candidates[@]} )); then
        _wt_enter "${candidates[$choice]}"
      else
        echo "❌ Invalid choice"; return 1
      fi ;;
  esac
}

# @desc Create a new feature worktree with agent identity
# @featured
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
  echo "💡 Next: Run ${CYAN}vup${NC} to initialize your cockpit."
}

# @desc Remove a worktree and its associated local branch
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

# @desc Initialize git identity in current worktree
wtinit() {
  local agent="${1:-claude}"
  [[ -d ".git" || -f ".git" ]] || vibe_die "Not in a git repo/worktree"
  local aname="Agent-${(C)agent}" aemail="agent-${agent}@vibecoding.ai"
  git config user.name "$aname"; git config user.email "$aemail"
  echo "✅ Identity: $aname <$aemail>"
}

# @desc Refresh current worktree identity and state
wtrenew() {
  local wt="${PWD##*/}"; echo "🔄 Refreshing: $wt"
  local name; name="$(git config user.name 2>/dev/null)"
  [[ -z "$name" ]] && { wtinit claude; return; }
  echo "✅ Identity OK: $name <$(git config user.email 2>/dev/null)>"
  echo "💡 Tips: Sync state with ${CYAN}vibe task sync${NC}"
}

# @desc Initialize a modular Tmux workspace for a worktree
# @featured
vup() {
  vibe_require tmux git || return 1
  local mode="dash" target="" agent="${VIBE_DEFAULT_TOOL:-claude}"
  
  # Parse modular subcommands
  case "${1:-}" in
    logs|tests|edit|all) mode="$1"; shift ;;
    -a|--all) mode="all"; shift ;;
    *) mode="dash" ;;
  esac
  
  target="${1:-}"
  # Auto-detect current worktree if target is empty
  if [[ -z "$target" ]]; then
    local gr; gr="$(git rev-parse --show-toplevel 2>/dev/null)"
    [[ -n "$gr" ]] && { target="${gr##*/}"; [[ "$target" != wt-* ]] && target="main"; } || target="main"
  fi

  local dir_path
  if [[ "$target" == "main" ]]; then dir_path="$VIBE_MAIN"
  elif [[ "$target" == /* ]]; then dir_path="$target"; target="${target##*/}"
  else
    local rr; rr="$(git rev-parse --show-toplevel 2>/dev/null)"
    dir_path="${rr:+${rr:h}/$target}"
    [[ -z "$dir_path" ]] && dir_path="$VIBE_REPO/$target"
  fi
  [[ -d "$dir_path" ]] || vibe_die "Not found: $dir_path"

  local agent_cmd
  case "$agent" in
    opencode) vibe_require opencode; agent_cmd="opencode" ;;
    codex)    vibe_require codex;    agent_cmd="codex --yes" ;;
    *)        vibe_require claude;   agent_cmd="claude --dangerously-skip-permissions --continue" ;;
  esac

  vibe_tmux_ensure || return 1

  case "$mode" in
    dash)
      local git_cmd="lazygit"; vibe_has lazygit || git_cmd="git status; zsh"
      vibe_tmux_dash "${target}-dash" "$dir_path" "$git_cmd" "$agent_cmd"
      ;;
    logs) vibe_tmux_win "${target}-logs" "$dir_path" ;;
    tests) vibe_tmux_win "${target}-tests" "$dir_path" ;;
    edit)  vibe_tmux_win "${target}-edit" "$dir_path" "${EDITOR:-vim}" ;;
    all)
      vibe_tmux_win "${target}-edit" "$dir_path" "${EDITOR:-vim}"
      vibe_tmux_win "${target}-agent" "$dir_path" "$agent_cmd"
      vibe_tmux_win "${target}-tests" "$dir_path"
      vibe_tmux_win "${target}-logs" "$dir_path"
      local git_cmd="lazygit"; vibe_has lazygit || git_cmd="git status; zsh"
      vibe_tmux_win "${target}-git" "$dir_path" "$git_cmd"
      vibe_tmux_dash "${target}-dash" "$dir_path" "$git_cmd" "$agent_cmd"
      ;;
  esac
  
  if [[ -n "$TMUX" ]]; then
    local cur_s; cur_s=$(tmux display-message -p '#S' 2>/dev/null)
    if [[ "$cur_s" != "$VIBE_SESSION" ]]; then
      echo "🚀 Teleporting to session: $VIBE_SESSION"
      tmux switch-client -t "$VIBE_SESSION"
    else
      echo "✅ Workspace [$mode] active: ${target}"
    fi
  else
    echo "🛫 Taking off to cockpit..."
    vibe_tmux_attach
  fi
}

# @desc One-shot command to create worktree and setup workspace
# @featured
vnew() {
  local branch="$1" agent="${2:-claude}" base="${3:-main}"
  [[ -z "$branch" ]] && vibe_die "usage: vnew <branch> [agent] [base]"
  wtnew "$branch" "$agent" "$base" || return 1
  vup "$agent" "$branch" || return 1
  
  if [[ -n "$TMUX" ]]; then
    echo "✅ Ready. Your dash window is active."
  else
    echo "✅ Ready. Run ${CYAN}vt${NC} to enter your new workspace."
  fi
}
