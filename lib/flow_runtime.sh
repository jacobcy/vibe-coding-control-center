#!/usr/bin/env zsh

_flow_now_iso() { date +"%Y-%m-%dT%H:%M:%S%z"; }

_flow_switch_target_branch() {
  local raw="$1" slug
  if [[ "$raw" == */* ]]; then
    echo "$raw"
    return 0
  fi
  slug="$(_vibe_task_slugify "$raw")"
  echo "task/$slug"
}

_flow_update_current_worktree_branch() {
  local branch="$1" git_common_dir worktrees_file current_dir current_path now tmp
  git_common_dir="$(git rev-parse --git-common-dir 2>/dev/null)" || return 0
  worktrees_file="$git_common_dir/vibe/worktrees.json"
  [[ -f "$worktrees_file" ]] || return 0

  current_dir="$(basename "$PWD")"
  current_path="$PWD"
  now="$(_flow_now_iso)"
  tmp="$(mktemp)" || return 1

  jq --arg wt "$current_dir" --arg path "$current_path" --arg branch "$branch" --arg now "$now" '
    .worktrees = (
      (.worktrees // []) as $items
      | if any($items[]?; .worktree_name == $wt or .worktree_path == $path) then
          $items | map(
            if .worktree_name == $wt or .worktree_path == $path then
              .branch = $branch
              | .worktree_name = $wt
              | .worktree_path = $path
              | .status = "active"
              | .last_updated = $now
            else . end
          )
        else
          $items + [{
            worktree_name: $wt,
            worktree_path: $path,
            branch: $branch,
            current_task: null,
            tasks: [],
            status: "active",
            dirty: false,
            agent: null,
            last_updated: $now
          }]
        end
    )
  ' "$worktrees_file" > "$tmp" && mv "$tmp" "$worktrees_file"
}

_flow_switch() {
  local forwarded=() target_seen=0
  for arg in "$@"; do [[ "$arg" == "-h" || "$arg" == "--help" ]] && { _flow_switch_usage; return 0; }; done

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --branch) forwarded+=("$1" "$2"); shift 2 ;;
      --save-stash) forwarded+=("--save-unstash"); shift ;;
      -*) log_error "Unknown option for flow switch: $1"; _flow_switch_usage; return 1 ;;
      *)
        if [[ $target_seen -eq 0 ]]; then
          forwarded+=("$1")
          target_seen=1
        fi
        shift
        ;;
    esac
  done

  _flow_new "${forwarded[@]}"
}
