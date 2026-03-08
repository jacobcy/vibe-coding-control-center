#!/usr/bin/env zsh
# tests/test_task_helper.zsh
# Shared helper functions for task tests

# Setup basic environment and source libs
setup_task_env() {
    export VIBE_ROOT="${VIBE_ROOT:-$(pwd)}"
    export VIBE_LIB="$VIBE_ROOT/lib"
    
    # Mock some basic vibe functions if needed or source them
    source "$VIBE_LIB/config.sh" 2>/dev/null || true
    source "$VIBE_LIB/utils.sh" 2>/dev/null || true
    source "$VIBE_LIB/task.sh"
}

# Create a standard task fixture in a temporary directory
make_task_fixture() {
    local fixture="$1"
    local worktree_path="$fixture/wt-test-task"

    mkdir -p "$fixture/vibe/tasks/old-task" "$fixture/vibe/tasks/2026-03-02-rotate-alignment" "$worktree_path"
    
    # Create worktrees.json
    cat > "$fixture/vibe/worktrees.json" <<JSON
{
  "schema_version": "v1",
  "worktrees": [
    {
      "worktree_name": "wt-test-task",
      "worktree_path": "$worktree_path",
      "branch": "feature/old-task",
      "current_task": "old-task",
      "tasks": ["old-task"],
      "status": "active",
      "dirty": false
    }
  ]
}
JSON

    # Create registry.json
    cat > "$fixture/vibe/registry.json" <<JSON
{
  "schema_version": "v1",
  "tasks": [
    {
      "task_id": "old-task",
      "title": "Old Task",
      "status": "done",
      "current_subtask_id": null,
      "assigned_worktree": "wt-test-task",
      "next_step": "Done."
    },
    {
      "task_id": "2026-03-02-rotate-alignment",
      "title": "Rotate Workflow Refinement",
      "status": "todo",
      "current_subtask_id": null,
      "assigned_worktree": null,
      "next_step": "Start here."
    }
  ]
}
JSON

    # Create individual task.json files
    printf '%s\n' '{"task_id":"old-task","title":"Old Task","status":"done","subtasks":[],"assigned_worktree":"wt-test-task","next_step":"Done."}' > "$fixture/vibe/tasks/old-task/task.json"
    printf '%s\n' '{"task_id":"2026-03-02-rotate-alignment","title":"Rotate Workflow Refinement","status":"todo","subtasks":[],"assigned_worktree":null,"next_step":"Start here."}' > "$fixture/vibe/tasks/2026-03-02-rotate-alignment/task.json"
}

# Helper to mock git behavior for registry access
mock_git_registry() {
    local fdir="$1"
    export _TEST_TASK_FIXTURE="$fdir"
    git() {
        case "$*" in
            "rev-parse --is-inside-work-tree") echo true; return 0 ;;
            "rev-parse --git-common-dir") echo "$_TEST_TASK_FIXTURE"; return 0 ;;
            "rev-parse --show-toplevel") 
                if [[ -d "$_TEST_TASK_FIXTURE/wt-test-task" ]]; then
                    echo "$_TEST_TASK_FIXTURE/wt-test-task"
                else
                    echo "$_TEST_TASK_FIXTURE"
                fi
                return 0 
                ;;

            "branch"*) return 1 ;;
            *) command git "$@" ;;
        esac
    }
}
