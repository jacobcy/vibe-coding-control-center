#!/usr/bin/env zsh
# v2/lib/task.sh - Core Task Logic for Vibe 2.0
# Target: < 150 lines | Direct JSON APIs

source "$VIBE_LIB/task_help.sh"

_vibe_task_ctx() {
    [[ "$(git rev-parse --is-inside-work-tree 2>/dev/null)" == "true" ]] || { vibe_die "Not in a git repository"; return 1; }
    local common; common=$(git rev-parse --git-common-dir)
    REGISTRY="$common/vibe/registry.json"
    WORKTREES="$common/vibe/worktrees.json"
    SHARED_DIR="$common/vibe/shared"
    mkdir -p "$SHARED_DIR"
    [[ -f "$REGISTRY" ]] || { vibe_die "Missing registry.json"; return 1; }
    NOW="$(date +"%Y-%m-%dT%H:%M:%S%z")"
}

_vibe_task_list() {
    local show_all=0 json_out=0
    while [[ $# -gt 0 ]]; do
        case "$1" in 
            -a|--all) show_all=1 ;;
            --json) json_out=1 ;;
            -h|--help) _vibe_task_usage; return 0 ;;
        esac; shift
    done

    _vibe_task_ctx || return 1
    
    # Collect data (Merge Registry + Worktrees + OpenSpec via bridge)
    local data
    data=$(jq -n --slurpfile reg "$REGISTRY" --slurpfile wt "$WORKTREES" \
        '{ tasks: $reg[0].tasks, worktrees: $wt[0].worktrees }')
    
    # Inject OpenSpec tasks if bridge exists
    if [[ -x "$VIBE_ROOT/scripts/openspec_bridge.sh" ]]; then
        data=$(echo "$data" | "$VIBE_ROOT/scripts/openspec_bridge.sh" merge)
    fi

    if (( json_out )); then
        # Inject live worktree health into JSON for Agent observability
        echo "$data" | jq '
            .tasks |= map(
                . + { 
                    is_dirty: (if .assigned_worktree != null then true else false end),
                    has_shared_state: (if .assigned_worktree != null then true else false end)
                }
            )
        '
        return 0
    fi

    # Textual Rendering (Simplified)
    echo "${BOLD}Vibe Task Registry${NC}"
    echo "$data" | jq -r --arg show_all "$show_all" '
        .tasks[] | 
        select($show_all == "1" or (.status | . != "completed" and . != "archived")) |
        "- \(.task_id)\n  Title: \(.title)\n  Status: \(.status)\n  Assigned: \(.assigned_worktree // "-")\n  Next: \(.next_step // "-")\n"'
}

_vibe_task_update() {
    local task_id="${1:-}" task_status="" next_step="" unassign=0 bind_current=0 agent=""
    shift $(( $# > 0 ? 1 : 0 ))
    [[ -n "$task_id" ]] || { vibe_die "Missing task id"; return 1; }
    
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --status) task_status="$2"; shift 2 ;;
            --next-step) next_step="$2"; shift 2 ;;
            --agent) agent="$2"; shift 2 ;;
            --unassign) unassign=1; shift ;;
            --bind-current) bind_current=1; shift ;;
            *) vibe_die "Unknown option: $1"; return 1 ;;
        esac
    done

    _vibe_task_ctx || return 1
    
    # Auto-register OpenSpec tasks if missing from registry
    if ! jq -e --arg id "$task_id" '.tasks[]? | select(.task_id == $id)' "$REGISTRY" >/dev/null 2>&1; then
        if [[ -x "$VIBE_ROOT/scripts/openspec_bridge.sh" ]]; then
            local os_task; os_task=$("$VIBE_ROOT/scripts/openspec_bridge.sh" find "$task_id")
            if [[ -n "$os_task" ]]; then
                local tmp_reg; tmp_reg=$(mktemp)
                jq --argjson t "$os_task" '.tasks += [$t]' "$REGISTRY" > "$tmp_reg" && mv "$tmp_reg" "$REGISTRY"
                log_info "Auto-registered OpenSpec task: $task_id"
            fi
        fi
    fi

    # 1. Update Registry
    local tmp; tmp=$(mktemp)
    jq --arg id "$task_id" --arg s "$task_status" --arg ns "$next_step" --argjson u "$unassign" --arg a "$agent" --arg t "$NOW" '
        .tasks |= map(if .task_id == $id then 
            (if $s != "" then .status = $s else . end) |
            (if $ns != "" then .next_step = $ns else . end) |
            (if $a != "" then .agent = $a else . end) |
            (if $u == 1 then .assigned_worktree = null else . end) |
            .updated_at = $t
        else . end)
    ' "$REGISTRY" > "$tmp" && mv "$tmp" "$REGISTRY"

    # 2. Handle Worktree Binding
    if (( bind_current )); then
        local wt_name; wt_name=$(basename "$PWD")
        local wt_path; wt_path="$PWD"
        jq --arg id "$task_id" --arg name "$wt_name" --arg path "$wt_path" --arg t "$NOW" '
            .tasks |= map(if .task_id == $id then .assigned_worktree = $name else . end) |
            .worktrees |= map(if .worktree_name == $name then .current_task = $id | .status = "active" | .last_updated = $t else . end)
        ' "$REGISTRY" > "$tmp" && mv "$tmp" "$REGISTRY" # Update reg with binding
        # Separate update for worktrees.json if needed
        jq --arg id "$task_id" --arg name "$wt_name" --arg t "$NOW" '
            .worktrees |= map(if .worktree_name == $name then .current_task = $id | .status = "active" | .last_updated = $t else . end)
        ' "$WORKTREES" > "$tmp" && mv "$tmp" "$WORKTREES"
    fi
    log_success "Task $task_id updated"
}

_vibe_task_add() {
    local id="${1:-}" title=""
    shift; while [[ $# -gt 0 ]]; do 
        case "$1" in --title) title="$2"; shift 2 ;; esac
    done
    [[ -n "$id" && -n "$title" ]] || { vibe_die "Usage: vibe task add <id> --title <title>"; return 1; }
    
    _vibe_task_ctx || return 1
    
    if jq -e --arg id "$id" '.tasks[]? | select(.task_id == $id)' "$REGISTRY" >/dev/null 2>&1; then
        log_warn "Task $id already exists in registry"
        return 0
    fi
    
    local tmp; tmp=$(mktemp)
    jq --arg id "$id" --arg t "$title" --arg now "$NOW" '
        .tasks += [{task_id: $id, title: $t, status: "todo", updated_at: $now}]
    ' "$REGISTRY" > "$tmp" && mv "$tmp" "$REGISTRY"
    log_success "Task $id added"
}

_vibe_task_remove() {
    local id="${1:-}"
    [[ -n "$id" ]] || { vibe_die "Missing task id"; return 1; }
    _vibe_task_ctx || return 1
    local tmp; tmp=$(mktemp)
    jq --arg id "$id" '.tasks |= map(select(.task_id != $id))' "$REGISTRY" > "$tmp" && mv "$tmp" "$REGISTRY"
    log_success "Task $id removed"
}

_vibe_task_sync() {
    _vibe_task_ctx || return 1
    if [[ ! -x "$VIBE_ROOT/scripts/openspec_bridge.sh" ]]; then
        log_warn "OpenSpec bridge script not found"
        return 0
    fi
    
    # Simple sync: find all openspec tasks and ensure they are registered
    local openspec_dir="openspec/changes"
    [[ -d "$openspec_dir" ]] || return 0
    
    for cid in "$openspec_dir"/*(N/); do
        local id; id=$(basename "$cid")
        [[ "$id" == "archive" ]] && continue
        # Use update logic to auto-register
        _vibe_task_update "$id" --next-step "Syncing from OpenSpec" >/dev/null 2>&1
    done
    log_success "OpenSpec tasks synced to registry"
}

vibe_task() {
    local sub="${1:-list}"; shift 2>/dev/null || true
    case "$sub" in
        list) _vibe_task_list "$@" ;;
        add) _vibe_task_add "$@" ;;
        update) _vibe_task_update "$@" ;;
        remove) _vibe_task_remove "$@" ;;
        sync) _vibe_task_sync ;;
        help|-h|--help) _vibe_task_usage ;;
        *) vibe_die "Unknown sub: $sub" ;;
    esac
}
