#!/usr/bin/env zsh
_vibe_task_common_dir() { git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { vibe_die "Not in a git repository"; return 1; }; git rev-parse --git-common-dir; }
_vibe_task_now() { date +"%Y-%m-%dT%H:%M:%S%z"; }
_vibe_task_slugify() { print -r -- "$1" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//'; }
_vibe_task_require_file() { [[ -f "$1" ]] || { vibe_die "Missing $2: $1"; return 1; }; }
_vibe_task_task_file() { echo "$1/vibe/tasks/$2/task.json"; }
_vibe_task_usage() { echo "Usage: vibe task [list] [-a|--all]"; echo "       vibe task add [options]"; echo "       vibe task update <task-id> [options]"; echo "       vibe task remove <task-id>"; }
_vibe_task_collect_openspec_tasks() {
    local repo_root="$1" changes_dir="$repo_root/openspec/changes" aggregate_file change_dir change_name tasks_file total_tasks done_tasks change_status next_step
    [[ -d "$changes_dir" ]] || { echo '{"tasks":[]}'; return 0; }
    aggregate_file="$(mktemp)" || return 1
    echo '[]' > "$aggregate_file"
    for change_dir in "$changes_dir"/*(N); do
        [[ -d "$change_dir" ]] || continue
        change_name="$(basename "$change_dir")"
        [[ "$change_name" == "archive" ]] && continue
        tasks_file="$change_dir/tasks.md"; total_tasks=0; done_tasks=0
        if [[ -f "$tasks_file" ]]; then total_tasks="$(grep -E '^- \[( |x|X)\]' "$tasks_file" | wc -l | tr -d ' ')"; done_tasks="$(grep -E '^- \[[xX]\]' "$tasks_file" | wc -l | tr -d ' ')"; fi
        if [[ "$total_tasks" -gt 0 && "$done_tasks" -eq "$total_tasks" ]]; then change_status="completed"; elif [[ "$done_tasks" -gt 0 ]]; then change_status="in-progress"; else change_status="todo"; fi
        next_step="Continue OpenSpec change: openspec/changes/$change_name/tasks.md"
        jq --arg task_id "$change_name" --arg title "$change_name" --arg framework "openspec" --arg source_path "openspec/changes/$change_name" --arg status "$change_status" --arg next_step "$next_step" '. += [{task_id:$task_id,title:$title,framework:$framework,source_path:$source_path,status:$status,current_subtask_id:null,assigned_worktree:null,next_step:$next_step}]' "$aggregate_file" > "$aggregate_file.tmp" && mv "$aggregate_file.tmp" "$aggregate_file"
    done
    jq -n --slurpfile tasks "$aggregate_file" '{"tasks":($tasks[0] // [])}'
    rm -f "$aggregate_file"
}
_vibe_task_render() {
    local worktrees_file="$1" registry_file="$2" openspec_tasks_file="$3" show_all="$4"
    echo "==== Vibe Task Overview ===="; echo ""; echo "--- Active Worktrees ---"
    jq -r --slurpfile registry "$registry_file" --slurpfile openspec "$openspec_tasks_file" '((($registry[0].tasks // []) + ($openspec[0].tasks // []) | unique_by(.task_id)) as $all | ([.worktrees[]?] | if length == 0 then ["  (No active worktrees)",""] else map(. as $w | ($all | map(select(.task_id == $w.current_task)) | .[0]) as $t | ["- \($w.worktree_name // "-")","  path: \($w.worktree_path // "-")","  branch: \($w.branch // "-")","  state: \($w.status // "-") \(if $w.dirty then "dirty" else "clean" end)","  task: \($w.current_task // "-")","  title: \($t.title // "-")","  framework: \($t.framework // "vibe")","  source: \($t.source_path // "-")","  status: \($t.status // "-")","  current subtask: \($t.current_subtask_id // "-")","  next step: \($t.next_step // "-")",""]) | flatten end)) | .[]' "$worktrees_file"
    echo "--- Task Registry Overview ---"
    jq -r --slurpfile openspec "$openspec_tasks_file" --arg show_all "$show_all" '(((.tasks // []) + ($openspec[0].tasks // []) | unique_by(.task_id)) as $all | ([$all[] | select($show_all == "1" or ((.status // "") != "completed" and (.status // "") != "archived" and (.status // "") != "done" and (.status // "") != "skipped"))] | if length == 0 then ["  (No tasks found matching criteria)",""] else map(["- \(.task_id // "-")","  title: \(.title // "-")","  framework: \(.framework // "vibe")","  source: \(.source_path // "-")","  status: \(.status // "-")","  assigned: \(.assigned_worktree // "-")","  subtask: \(.current_subtask_id // "-")","  next step: \(.next_step // "-")",""]) | flatten end)) | .[]' "$registry_file"
}
_vibe_task_list() {
    local common_dir worktrees_file registry_file show_all="0" missing openspec_tasks_file repo_root
    for arg in "$@"; do case "$arg" in -a|--all) show_all="1" ;; -h|--help) _vibe_task_usage; echo "  Show active worktrees and tasks in the registry."; echo "  -a, --all    Show all tasks including completed/archived."; return 0 ;; *) vibe_die "Unknown list option: $arg"; return 1 ;; esac; done
    vibe_require git jq || return 1
    common_dir="$(_vibe_task_common_dir)" || return 1; worktrees_file="$common_dir/vibe/worktrees.json"; registry_file="$common_dir/vibe/registry.json"
    _vibe_task_require_file "$worktrees_file" "worktrees.json" || return 1; _vibe_task_require_file "$registry_file" "registry.json" || return 1
    repo_root="$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")"; openspec_tasks_file="$(mktemp)" || return 1
    _vibe_task_collect_openspec_tasks "$repo_root" > "$openspec_tasks_file"
    missing="$(jq -r --slurpfile registry "$registry_file" --slurpfile openspec "$openspec_tasks_file" '((($registry[0].tasks // []) + ($openspec[0].tasks // []) | unique_by(.task_id)) as $all | [.worktrees[]? as $w | select($w.current_task != null) | select(($all | map(.task_id) | index($w.current_task)) == null) | $w.current_task] | unique[])' "$worktrees_file")" || { rm -f "$openspec_tasks_file"; return 1; }
    [[ -z "$missing" ]] || { rm -f "$openspec_tasks_file"; vibe_die "Task not found in registry: ${missing%%$'\n'*}"; return 1; }
    _vibe_task_render "$worktrees_file" "$registry_file" "$openspec_tasks_file" "$show_all"
    rm -f "$openspec_tasks_file"
}
_vibe_task_write_registry() {
    local registry_file="$1" task_id="$2" task_status="$3" next_step="$4" assigned="$5" agent="$6" now="$7" tmp
    tmp="$(mktemp)" || return 1
    jq --arg task_id "$task_id" --arg task_status "$task_status" --arg next_step "$next_step" --arg assigned "$assigned" --arg agent "$agent" --arg now "$now" '
      .tasks |= map(if .task_id == $task_id then
        (if $task_status != "" then .status = $task_status else . end)
        | (if $next_step != "" then .next_step = $next_step else . end)
        | (if $assigned != "" then .assigned_worktree = $assigned else . end)
        | (if $agent != "" then .agent = $agent else . end)
        | .updated_at = $now
      else . end)
    ' "$registry_file" >"$tmp" && mv "$tmp" "$registry_file"
}
_vibe_task_write_worktrees() {
    local worktrees_file="$1" target_name="$2" target_path="$3" task_id="$4" branch="$5" agent="$6" bind_current="$7" now="$8" tmp
    [[ -n "$target_name" || -n "$target_path" ]] || return 0
    tmp="$(mktemp)" || return 1
    jq --arg target_name "$target_name" --arg target_path "$target_path" --arg task_id "$task_id" --arg branch "$branch" --arg agent "$agent" --arg now "$now" --argjson bind_current "$bind_current" '
      .worktrees = ((.worktrees // []) as $items | ([ $items[] | select(.worktree_name == $target_name or ($target_path != "" and .worktree_path == $target_path)) ] | length) as $hits
        | if $hits == 0 and $bind_current then
            $items + [{worktree_name:$target_name, worktree_path:$target_path, branch:($branch | select(. != "")), current_task:$task_id, status:"active", dirty:false, agent:($agent | select(. != "")), last_updated:$now}]
          else
            $items | map(if .worktree_name == $target_name or ($target_path != "" and .worktree_path == $target_path) then
              (if $target_path != "" then .worktree_path = $target_path else . end)
              | (if $branch != "" then .branch = $branch else . end)
              | (if $agent != "" then .agent = $agent else . end)
              | (if $bind_current then .current_task = $task_id | .status = "active" else . end)
              | .last_updated = $now
            else . end)
          end)
    ' "$worktrees_file" >"$tmp" && mv "$tmp" "$worktrees_file"
}
_vibe_task_write_task_file() {
    local common_dir="$1" registry_file="$2" task_id="$3" now="$4" task_file tmp
    local task_title task_status next_step assigned
    task_file="$(_vibe_task_task_file "$common_dir" "$task_id")"
    task_title="$(jq -r --arg task_id "$task_id" '.tasks[] | select(.task_id == $task_id) | .title // ""' "$registry_file")"
    task_status="$(jq -r --arg task_id "$task_id" '.tasks[] | select(.task_id == $task_id) | .status // "todo"' "$registry_file")"
    next_step="$(jq -r --arg task_id "$task_id" '.tasks[] | select(.task_id == $task_id) | .next_step // ""' "$registry_file")"
    assigned="$(jq -r --arg task_id "$task_id" '.tasks[] | select(.task_id == $task_id) | .assigned_worktree // ""' "$registry_file")"
    mkdir -p "$(dirname "$task_file")"
    tmp="$(mktemp)" || return 1
    if [[ -f "$task_file" ]]; then
        jq --arg task_id "$task_id" --arg task_title "$task_title" --arg task_status "$task_status" --arg next_step "$next_step" --arg assigned "$assigned" --arg now "$now" '
          .task_id = $task_id
          | .title = (if (.title // "") == "" then $task_title else .title end)
          | .subtasks = (.subtasks // [])
          | .status = $task_status
          | .assigned_worktree = (if $assigned == "" then null else $assigned end)
          | .next_step = $next_step
          | .updated_at = $now
        ' "$task_file" >"$tmp" && mv "$tmp" "$task_file"
    else
        jq -n --arg task_id "$task_id" --arg task_title "$task_title" --arg task_status "$task_status" --arg next_step "$next_step" --arg assigned "$assigned" --arg now "$now" '
          {
            task_id: $task_id,
            title: $task_title,
            status: $task_status,
            subtasks: [],
            assigned_worktree: (if $assigned == "" then null else $assigned end),
            next_step: $next_step,
            updated_at: $now
          }
        ' >"$tmp" && mv "$tmp" "$task_file"
    fi
}
_vibe_task_refresh_cache() {
    local common_dir="$1" registry_file="$2" task_id="$3" worktree_name="$4" now="$5" task_path title next_step subtask_json
    local vibe_dir=".vibe"; mkdir -p "$vibe_dir"; task_path="$common_dir/vibe/tasks/$task_id/task.json"
    title="$(jq -r --arg task_id "$task_id" '.tasks[] | select(.task_id == $task_id) | .title // ""' "$registry_file")"
    next_step="$(jq -r --arg task_id "$task_id" '.tasks[] | select(.task_id == $task_id) | .next_step // ""' "$registry_file")"
    subtask_json="$(jq -c --arg task_id "$task_id" '.tasks[] | select(.task_id == $task_id) | (.current_subtask_id // null)' "$registry_file")"
    jq -n --arg task_id "$task_id" --arg task_path "$task_path" --arg registry_path "$registry_file" --arg worktree_name "$worktree_name" --arg updated_at "$now" '{task_id:$task_id, task_path:$task_path, registry_path:$registry_path, worktree_name:$worktree_name, updated_at:$updated_at}' > "$vibe_dir/current-task.json"
    cat > "$vibe_dir/focus.md" <<EOF
# Focus

- task: $task_id
- title: $title
- next_step: $next_step
EOF
    jq -n --arg worktree_name "$worktree_name" --arg current_task "$task_id" --arg saved_at "$now" --argjson current_subtask_id "${subtask_json:-null}" '{worktree_name:$worktree_name, current_task:$current_task, current_subtask_id:$current_subtask_id, saved_at:$saved_at}' > "$vibe_dir/session.json"
}
_vibe_task_update() {
    local task_id="${1:-}" task_status="" agent="" worktree="" branch="" next_step="" bind_current=0 force=0 common_dir registry_file worktrees_file now target_name="" target_path="" email_slug=""
    shift $(( $# > 0 ? 1 : 0 ))
    [[ "$task_id" == "-h" || "$task_id" == "--help" ]] && { echo "Usage: vibe task update <task-id> [options]"; echo "  Supported fields: --status --agent --worktree --branch --bind-current --next-step"; return 0; }
    [[ -n "$task_id" ]] || { vibe_die "Missing task id for update"; return 1; }
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --status|--agent|--worktree|--branch|--next-step) [[ $# -ge 2 ]] || { vibe_die "Missing value for $1"; return 1; }; case "$1" in --status) task_status="$2" ;; --agent) agent="$2" ;; --worktree) worktree="$2" ;; --branch) branch="$2" ;; --next-step) next_step="$2" ;; esac; shift 2 ;;
            --bind-current) bind_current=1; shift ;;
            -f|--force) force=1; shift ;;
            -h|--help) echo "Usage: vibe task update <task-id> [options]"; echo "  Supported fields: --status --agent --worktree --branch --bind-current --next-step"; return 0 ;;
            *) vibe_die "Unknown update option: $1"; return 1 ;;
        esac
    done
    [[ -n "$task_status$agent$worktree$branch$next_step" || "$bind_current" -eq 1 ]] || { vibe_die "No update fields provided"; return 1; }
    vibe_require git jq || return 1
    common_dir="$(_vibe_task_common_dir)" || return 1; registry_file="$common_dir/vibe/registry.json"; worktrees_file="$common_dir/vibe/worktrees.json"; now="$(_vibe_task_now)"
    _vibe_task_require_file "$registry_file" "registry.json" || return 1; _vibe_task_require_file "$worktrees_file" "worktrees.json" || return 1
    jq -e --arg task_id "$task_id" '.tasks[]? | select(.task_id == $task_id)' "$registry_file" >/dev/null 2>&1 || { vibe_die "Task not found in registry: $task_id"; return 1; }
    if [[ -n "$agent" ]]; then
        case "$agent" in codex|antigravity|trae|claude|opencode|kiro) ;; *) [[ "$force" -eq 1 ]] || { vibe_die "Unsupported agent: $agent"; return 1; } ;; esac
        email_slug="$agent"; [[ "$force" -eq 1 ]] && email_slug="$(_vibe_task_slugify "$agent")"
        git config user.name "$agent" 2>/dev/null || git config user.name "$agent" || return 1
        git config user.email "${email_slug}@vibe.coding" 2>/dev/null || git config user.email "${email_slug}@vibe.coding" || return 1
    fi
    [[ "$bind_current" -eq 1 ]] && { target_name="$(basename "$PWD")"; target_path="$PWD"; worktree="$target_name"; }
    [[ -z "$target_name" ]] && target_name="$worktree"
    _vibe_task_write_registry "$registry_file" "$task_id" "$task_status" "$next_step" "$worktree" "$agent" "$now" || return 1
    _vibe_task_write_task_file "$common_dir" "$registry_file" "$task_id" "$now" || return 1
    _vibe_task_write_worktrees "$worktrees_file" "$target_name" "$target_path" "$task_id" "$branch" "$agent" "$bind_current" "$now" || return 1
    [[ "$bind_current" -eq 1 ]] && _vibe_task_refresh_cache "$common_dir" "$registry_file" "$task_id" "$target_name" "$now"
    return 0
}
_vibe_task_add() {
    local task_id="${1:-}" title="" task_status="todo" next_step="" common_dir registry_file task_file now tmp
    [[ "$task_id" == "-h" || "$task_id" == "--help" ]] && { echo "Usage: vibe task add <task-id> --title <title> [--status <status>] [--next-step <text>]"; echo "  Register a task in the shared registry."; return 0; }
    [[ -n "$task_id" ]] || { vibe_die "Missing task id for add"; return 1; }
    shift
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --title|--status|--next-step) [[ $# -ge 2 ]] || { vibe_die "Missing value for $1"; return 1; }; case "$1" in --title) title="$2" ;; --status) task_status="$2" ;; --next-step) next_step="$2" ;; esac; shift 2 ;;
            *) vibe_die "Unknown add option: $1"; return 1 ;;
        esac
    done
    [[ -n "$title" ]] || { vibe_die "Missing --title for add"; return 1; }
    vibe_require git jq || return 1
    common_dir="$(_vibe_task_common_dir)" || return 1; registry_file="$common_dir/vibe/registry.json"; task_file="$(_vibe_task_task_file "$common_dir" "$task_id")"; now="$(_vibe_task_now)"
    _vibe_task_require_file "$registry_file" "registry.json" || return 1
    jq -e --arg task_id "$task_id" '.tasks[]? | select(.task_id == $task_id)' "$registry_file" >/dev/null 2>&1 && { vibe_die "Task already exists: $task_id"; return 1; }
    mkdir -p "$(dirname "$task_file")"; tmp="$(mktemp)" || return 1
    jq --arg task_id "$task_id" --arg title "$title" --arg task_status "$task_status" --arg next_step "$next_step" --arg now "$now" '.tasks += [{task_id:$task_id,title:$title,status:$task_status,current_subtask_id:null,assigned_worktree:null,next_step:$next_step,updated_at:$now}]' "$registry_file" > "$tmp" && mv "$tmp" "$registry_file" || return 1
    jq -n --arg task_id "$task_id" --arg title "$title" --arg task_status "$task_status" --arg next_step "$next_step" '{task_id:$task_id,title:$title,status:$task_status,subtasks:[],assigned_worktree:null,next_step:$next_step}' > "$task_file"
}
_vibe_task_remove() {
    local task_id="${1:-}" common_dir registry_file worktrees_file task_file tmp
    [[ "$task_id" == "-h" || "$task_id" == "--help" ]] && { echo "Usage: vibe task remove <task-id>"; echo "  Remove a task from the shared registry."; return 0; }
    [[ -n "$task_id" ]] || { vibe_die "Missing task id for remove"; return 1; }
    vibe_require git jq || return 1
    common_dir="$(_vibe_task_common_dir)" || return 1; registry_file="$common_dir/vibe/registry.json"; worktrees_file="$common_dir/vibe/worktrees.json"; task_file="$(_vibe_task_task_file "$common_dir" "$task_id")"
    _vibe_task_require_file "$registry_file" "registry.json" || return 1; _vibe_task_require_file "$worktrees_file" "worktrees.json" || return 1
    jq -e --arg task_id "$task_id" '.tasks[]? | select(.task_id == $task_id)' "$registry_file" >/dev/null 2>&1 || { vibe_die "Task not found in registry: $task_id"; return 1; }
    jq -e --arg task_id "$task_id" '.worktrees[]? | select(.current_task == $task_id)' "$worktrees_file" >/dev/null 2>&1 && { vibe_die "Task is still bound to a worktree: $task_id"; return 1; }
    tmp="$(mktemp)" || return 1
    jq --arg task_id "$task_id" '.tasks |= map(select(.task_id != $task_id))' "$registry_file" > "$tmp" && mv "$tmp" "$registry_file" || return 1
    rm -f "$task_file"; rmdir "$(dirname "$task_file")" 2>/dev/null || true
}
vibe_task() { local subcommand="${1:-list}"
    case "$subcommand" in
        list) shift; _vibe_task_list "$@" ;; add) shift; _vibe_task_add "$@" ;; update) shift; _vibe_task_update "$@" ;;
        remove) shift; _vibe_task_remove "$@" ;; -h|--help) _vibe_task_usage ;; -*) _vibe_task_list "$@" ;;
        "") _vibe_task_list ;; *) vibe_die "Unknown task subcommand: $subcommand"; return 1 ;;
    esac
}
