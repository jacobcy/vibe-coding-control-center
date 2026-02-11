#!/usr/bin/env zsh
# lib/flow_state.sh
# Workflow state management for vibe flow

# Get the flow state directory
get_flow_state_dir() {
    local vibe_home="${VIBE_HOME:-$HOME/.vibe}"
    echo "$vibe_home/flow"
}

# Get the flow state file path for a feature
get_flow_state_file() {
    local feature="$1"
    [[ -z "$feature" ]] && { log_error "Feature name required"; return 1; }
    
    local state_dir=$(get_flow_state_dir)
    echo "$state_dir/${feature}.json"
}

# Detect current feature from worktree directory name
detect_current_feature() {
    local dir_name=$(basename "$PWD")
    
    # Pattern: wt-<agent>-<feature>
    if [[ "$dir_name" =~ ^wt-([^-]+)-(.+)$ ]]; then
        echo "${match[2]}"
        return 0
    fi
    
    # Pattern: wt-<feature>
    if [[ "$dir_name" =~ ^wt-(.+)$ ]]; then
        echo "${match[1]}"
        return 0
    fi
    
    return 1
}

# Initialize a new flow state for a feature
flow_state_init() {
    local feature="$1"
    local branch="$2"
    local worktree="$3"
    local agent="${4:-claude}"
    
    [[ -z "$feature" ]] && { log_error "Feature name required"; return 1; }
    [[ -z "$branch" ]] && { log_error "Branch name required"; return 1; }
    [[ -z "$worktree" ]] && { log_error "Worktree path required"; return 1; }
    
    local state_dir=$(get_flow_state_dir)
    mkdir -p "$state_dir"
    
    local state_file=$(get_flow_state_file "$feature")
    
    if [[ -f "$state_file" ]]; then
        log_warn "Flow state already exists for feature: $feature"
        return 1
    fi
    
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    
    # Create JSON state file
    cat > "$state_file" <<EOF
{
  "feature": "$feature",
  "branch": "$branch",
  "worktree": "$worktree",
  "agent": "$agent",
  "created_at": "$timestamp",
  "updated_at": "$timestamp",
  "current_phase": "started",
  "prd_path": null,
  "spec_path": null,
  "test_path": null,
  "checklist": {
    "prd_created": false,
    "spec_written": false,
    "tests_initialized": false,
    "tests_passing": false,
    "code_reviewed": false,
    "pr_created": false,
    "pr_merged": false
  },
  "commits": [],
  "pr_url": null
}
EOF
    
    log_success "Initialized flow state: $state_file"
    return 0
}

# Update a specific field in the flow state
flow_state_update() {
    local feature="$1"
    local field="$2"
    local value="$3"
    
    [[ -z "$feature" ]] && { log_error "Feature name required"; return 1; }
    [[ -z "$field" ]] && { log_error "Field name required"; return 1; }
    
    local state_file=$(get_flow_state_file "$feature")
    
    if [[ ! -f "$state_file" ]]; then
        log_error "Flow state not found for feature: $feature"
        return 1
    fi
    
    # Update timestamp
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    
    # Use jq to update the field if available, otherwise use sed
    if command -v jq &>/dev/null; then
        local temp_file=$(mktemp)
        jq --arg val "$value" --arg ts "$timestamp" \
            ".${field} = \$val | .updated_at = \$ts" \
            "$state_file" > "$temp_file"
        mv "$temp_file" "$state_file"
    else
        # Fallback: manual JSON manipulation (limited)
        log_warn "jq not available, using basic update"
        # Just log the update for now
        echo "# Updated $field = $value at $timestamp" >> "${state_file}.log"
    fi
    
    return 0
}

# Update checklist item
flow_state_checklist() {
    local feature="$1"
    local item="$2"
    local value="${3:-true}"
    
    [[ -z "$feature" ]] && { log_error "Feature name required"; return 1; }
    [[ -z "$item" ]] && { log_error "Checklist item required"; return 1; }
    
    local state_file=$(get_flow_state_file "$feature")
    
    if [[ ! -f "$state_file" ]]; then
        log_error "Flow state not found for feature: $feature"
        return 1
    fi
    
    # Update timestamp
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    
    if command -v jq &>/dev/null; then
        local temp_file=$(mktemp)
        jq --arg item "$item" --argjson val "$value" --arg ts "$timestamp" \
            ".checklist[\$item] = \$val | .updated_at = \$ts" \
            "$state_file" > "$temp_file"
        mv "$temp_file" "$state_file"
    else
        log_warn "jq not available, checklist update skipped"
    fi
    
    return 0
}

# Get a field value from flow state
flow_state_get() {
    local feature="$1"
    local field="$2"
    
    [[ -z "$feature" ]] && { log_error "Feature name required"; return 1; }
    
    local state_file=$(get_flow_state_file "$feature")
    
    if [[ ! -f "$state_file" ]]; then
        log_error "Flow state not found for feature: $feature"
        return 1
    fi
    
    if command -v jq &>/dev/null; then
        if [[ -n "$field" ]]; then
            jq -r ".${field}" "$state_file"
        else
            cat "$state_file"
        fi
    else
        # Fallback: just cat the file
        if [[ -z "$field" ]]; then
            cat "$state_file"
        else
            log_error "jq required for field extraction"
            return 1
        fi
    fi
    
    return 0
}

# List all active flow states
flow_state_list() {
    local state_dir=$(get_flow_state_dir)
    
    if [[ ! -d "$state_dir" ]]; then
        log_info "No active workflows"
        return 0
    fi
    
    local found=0
    for state_file in "$state_dir"/*.json(N); do
        if [[ -f "$state_file" ]]; then
            local feature=$(basename "$state_file" .json)
            echo "$feature"
            found=1
        fi
    done
    
    if [[ $found -eq 0 ]]; then
        log_info "No active workflows"
    fi
    
    return 0
}

# Delete flow state for a feature
flow_state_delete() {
    local feature="$1"
    
    [[ -z "$feature" ]] && { log_error "Feature name required"; return 1; }
    
    local state_file=$(get_flow_state_file "$feature")
    
    if [[ ! -f "$state_file" ]]; then
        log_warn "Flow state not found for feature: $feature"
        return 0
    fi
    
    rm -f "$state_file"
    log_success "Deleted flow state for: $feature"
    return 0
}

# Archive flow state (move to archive directory)
flow_state_archive() {
    local feature="$1"
    
    [[ -z "$feature" ]] && { log_error "Feature name required"; return 1; }
    
    local state_file=$(get_flow_state_file "$feature")
    
    if [[ ! -f "$state_file" ]]; then
        log_error "Flow state not found for feature: $feature"
        return 1
    fi
    
    local state_dir=$(get_flow_state_dir)
    local archive_dir="$state_dir/archive"
    mkdir -p "$archive_dir"
    
    local timestamp=$(date +"%Y%m%d_%H%M%S")
    local archive_file="$archive_dir/${feature}_${timestamp}.json"
    
    mv "$state_file" "$archive_file"
    log_success "Archived flow state: $archive_file"
    return 0
}
