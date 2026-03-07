#!/usr/bin/env zsh
# Worktree management commands

# @desc List all worktrees
# @featured
alias wtls='git worktree list'

# ── Shared worktree finding logic ───────────────────────────────────────────
# Returns worktree path(s) matching the given name/pattern
# Usage: _wt_find "name" → prints path(s)
_wt_find() {
  local target="$1"
  local git_cmd; git_cmd="$(vibe_find_cmd git)" || return 1
  local awk_cmd; awk_cmd="$(vibe_find_cmd awk)" || return 1

  local main_dir; main_dir="$($git_cmd rev-parse --show-toplevel 2>/dev/null)"
  [[ -z "$main_dir" ]] && return 1

  local -a all_paths=()
  while IFS= read -r p; do
    [[ -n "$p" ]] && all_paths+=("$p")
  done < <($git_cmd -C "$main_dir" worktree list --porcelain 2>/dev/null | $awk_cmd '/^worktree /{print substr($0,10)}')

  [[ ${#all_paths[@]} -eq 0 ]] && return 1

  # ① Exact match: full basename or absolute path
  local p b
  for p in "${all_paths[@]}"; do
    b="${p##*/}"
    [[ "$b" == "$target" || "$p" == "$target" ]] && { echo "$p"; return 0; }
  done

  # ② Suffix match: basename ends with "-<target>"
  local -a candidates=()
  for p in "${all_paths[@]}"; do
    [[ "${p##*/}" == *"-${target}" ]] && candidates+=("$p")
  done

  # ③ Substring fallback: basename contains "<target>"
  if [[ ${#candidates[@]} -eq 0 ]]; then
    for p in "${all_paths[@]}"; do
      [[ "${p##*/}" == *"${target}"* ]] && candidates+=("$p")
    done
  fi

  printf '%s\n' "${candidates[@]}"
}

# @desc Jump to a specific worktree by name (e.g. wt my-feat)
# @featured
wt() {
  local target="$1"
  [[ -z "$target" ]] && { git worktree list; return; }

  _wt_enter() {
    local p="$1" label="${1##*/}"
    cd "$p" || return 1
    [[ -n "$TMUX" ]] && tmux rename-window "$label"
    echo "→ $label"
  }

  local result=$(_wt_find "$target")
  [[ -z "$result" ]] && { echo "❌ Worktree not found: $target"; git worktree list | sed 's/^/   /'; return 1; }

  local -a matches=(${(f)result})
    case ${#matches[@]} in
      0) echo "❌ Worktree not found: $target"; git worktree list | sed 's/^/   /'; return 1 ;;
      1) _wt_enter "${matches[1]}" ;;
      *)
        echo "🔍 Multiple worktrees match '${target}':"
        for p in "${matches[@]}"; do
          echo "  • ${p##*/}   ($p)"
        done
        echo "📌 Rerun wt with the exact worktree name (or full path)."
        return 1
        ;;
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
  local path="${repo_root}/.worktrees/$dir"

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
# @desc Remove a worktree and its associated local branch
wtrm() {
  local git_cmd; git_cmd="$(vibe_find_cmd git)" || { vibe_die "git not found"; return 1; }
  local awk_cmd; awk_cmd="$(vibe_find_cmd awk)" || { vibe_die "awk not found"; return 1; }
  local rm_cmd; rm_cmd="$(vibe_find_cmd rm)" || { vibe_die "rm not found"; return 1; }
  local assume_yes=false delete_remote=false target=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -y|--yes)
        assume_yes=true
        shift
        ;;
      -r|--delete-remote)
        delete_remote=true
        shift
        ;;
      -h|--help)
        vibe_die "usage: wtrm [--yes] [--delete-remote] <wt-dir|path|all|wildcard>"
        ;;
      *)
        if [[ -n "$target" ]]; then
          vibe_die "Unexpected argument: $1"
        fi
        target="$1"
        shift
        ;;
    esac
  done
  [[ -n "$target" ]] || vibe_die "usage: wtrm [--yes] [--delete-remote] <wt-dir|path|all|wildcard>"

  local main_dir; main_dir="$($git_cmd rev-parse --show-toplevel 2>/dev/null)" || { vibe_die "Not in git repo"; return 1; }

  _wtrm_one() {
    local p="$1" label="${1##*/}"
    [[ "$p" == "$main_dir" ]] && { echo "⚠️  Cannot remove main worktree"; return 1; }

    local branch_name=""
    if [[ -d "$p" ]]; then
      branch_name=$($git_cmd -C "$p" rev-parse --abbrev-ref HEAD 2>/dev/null)
    fi
    if [[ -z "$branch_name" ]]; then
      branch_name=$($git_cmd -C "$main_dir" worktree list --porcelain | $awk_cmd -v path="$p" '
        /^worktree / { if (substr($0,10) == path) found=1; else found=0 }
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
          if [[ "$delete_remote" == true ]]; then
            if $git_cmd -C "$main_dir" push origin --delete "$branch_name" >/dev/null 2>&1; then
              echo "🗑️  Deleted remote branch: origin/$branch_name"
            else
              log_warn "Failed to delete remote branch: origin/$branch_name"
            fi
          else
            echo "ℹ️  Remote branch origin/$branch_name still exists; rerun with --delete-remote to remove it."
          fi
        fi
      fi
    elif [[ -d "$p" ]]; then
      $rm_cmd -rf "$p"
      echo "🗑️  Deleted orphan: $label"
    else
      echo "⚠️  Not found: $p"
    fi
  }


  if [[ "$target" == "all" ]]; then
    local -a paths=()
    while IFS= read -r wp; do
      [[ "$wp" == "$main_dir" ]] && continue
      [[ "${wp##*/}" == wt-* ]] && paths+=("$wp")
    done < <($git_cmd -C "$main_dir" worktree list --porcelain | $awk_cmd '/^worktree /{print substr($0,10)}')
    [[ ${#paths[@]} -eq 0 ]] && { echo "ℹ️  No wt-* worktrees"; return 0; }
    [[ "$assume_yes" == true ]] || { echo "⚠️  wtrm --yes all will remove ${#paths[@]} worktrees. Rerun with --yes to confirm."; return 1; }
    echo "🗑️  Removing ${#paths[@]} worktree(s)..."
    for wp in "${paths[@]}"; do _wtrm_one "$wp"; done
  else
    local result=""
    # Wildcard path match (glob) goes through inline matcher.
    if [[ "$target" == *'*'* || "$target" == *'?'* ]]; then
      local safe_pattern="${target//\[/\\[}"; safe_pattern="${safe_pattern//\]/\\]}"
      local wp
      local -a glob_matches=()
      while IFS= read -r wp; do
        [[ "$wp" == "$main_dir" ]] && continue
        [[ "${wp##*/}" == $~safe_pattern ]] && glob_matches+=("$wp")
      done < <($git_cmd -C "$main_dir" worktree list --porcelain | $awk_cmd '/^worktree /{print substr($0,10)}')
      result="${(pj:\n:)glob_matches}"
    else
      # Default smart finder: exact/suffix/substring.
      result=$(_wt_find "$target")
    fi
    [[ -z "$result" ]] && { echo "❌ Worktree not found: $target"; git worktree list | sed 's/^/   /'; return 1; }

    local -a found_paths=(${(f)result})
    case ${#found_paths[@]} in
      0) echo "❌ Worktree not found: $target"; return 1 ;;
      1)
        [[ "$assume_yes" == true ]] || { echo "⚠️  wtrm requires --yes to remove worktree '${found_paths[1]}'. Rerun with --yes."; return 1; }
        _wtrm_one "${found_paths[1]}"
        ;;
      *)
        echo "🔍 Multiple worktrees match '${target}':"
        for p in "${found_paths[@]}"; do
          echo "  • ${p##*/}   ($p)"
        done
        echo "📌 Rerun wtrm with a more specific name or path."
        return 1
        ;;
    esac
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
#   vup              → current worktree
#   vup <name>       → smart match worktree from wtls
# @featured
vup() {
  vibe_require tmux git || return 1
  local mode="dash" target="" agent="${VIBE_DEFAULT_TOOL:-claude}"

  # Parse modular subcommands
  case "${1:-}" in
    logs|tests|edit|all) mode="$1"; shift ;;
    -a|--all) mode="all"; shift ;;
    *) ;;
  esac

  target="${1:-}"

  # Resolve target to directory path using _wt_find
  local dir_path
  if [[ -z "$target" ]]; then
    # No argument: use current git worktree root
    dir_path="$(git rev-parse --show-toplevel 2>/dev/null)" || {
      vibe_die "Not in a git worktree"
      return 1
    }
    target="${dir_path##*/}"
  else
    # Use _wt_find to locate worktree (supports exact/suffix/substring match)
    local result=$(_wt_find "$target")
    if [[ -n "$result" ]]; then
      local -a matches=(${(f)result})
      if [[ ${#matches[@]} -eq 1 ]]; then
        dir_path="${matches[1]}"
        target="${dir_path##*/}"
      else
        echo "🔍 Multiple worktrees match '${target}':"
        for p in "${matches[@]}"; do
          echo "  • ${p##*/}   ($p)"
        done
        echo "📌 Rerun vup with the full worktree name to pick the right target."
        return 1
      fi
    else
      vibe_die "Worktree not found: $target (checked wtls)"
      return 1
    fi
  fi

  [[ -d "$dir_path" ]] || {
    vibe_die "Not found: $dir_path"
    return 1
  }

  # Session name = worktree name (e.g., main, wt-claude-fix)
  local session_name="$target"
  local had_session=${+VIBE_SESSION}
  local old_session="$VIBE_SESSION"
  VIBE_SESSION="$session_name"

  local agent_cmd
  case "$agent" in
    opencode) vibe_require opencode; agent_cmd="opencode" ;;
    codex)    vibe_require codex;    agent_cmd="codex --yes" ;;
    *)        vibe_require claude;   agent_cmd="claude --dangerously-skip-permissions --continue" ;;
  esac

  # Create session if needed (don't destroy existing)
  if ! tmux has-session -t "$session_name" 2>/dev/null; then
    tmux new-session -d -s "$session_name" -c "$dir_path" -n "dash"
  else
    # Ensure session has a dash window
    if ! tmux list-windows -t "$session_name" -F "#{window_name}" 2>/dev/null | grep -qx "dash"; then
      tmux new-window -t "$session_name" -n "dash" -c "$dir_path"
    fi
  fi

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

  # Switch to the session (but don't change VIBE_SESSION env var permanently)
  if [[ -n "$TMUX" ]]; then
    local cur_s; cur_s=$(tmux display-message -p '#S' 2>/dev/null)
    if [[ "$cur_s" != "$session_name" ]]; then
      echo "🚀 Teleporting to session: $session_name"
      tmux switch-client -t "$session_name"
    else
      echo "✅ Workspace [$mode] active: ${target}"
    fi
  else
    echo "🛫 Taking off to cockpit..."
    tmux attach -t "$session_name"
  fi

  if (( had_session )); then
    VIBE_SESSION="$old_session"
  else
    unset VIBE_SESSION
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
