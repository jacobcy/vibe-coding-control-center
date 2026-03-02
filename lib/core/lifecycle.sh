#!/usr/bin/env zsh
# v3/lib/core/lifecycle.sh - Lifecycle Manager
# Manages command execution lifecycle and hooks

# ── Lifecycle State ───────────────────────────────────────
typeset -A _VIBE_BEFORE_HOOKS
typeset -A _VIBE_AFTER_HOOKS
typeset -i _VIBE_HOOK_COUNTER=0

# ── Hook Registration ─────────────────────────────────────
# Registers a before hook for a command
# Usage: vibe_register_before_hook <command> <function_name>
vibe_register_before_hook() {
    local command="$1"
    local hook_func="$2"

    if [[ -z "$command" || -z "$hook_func" ]]; then
        log_error "Usage: vibe_register_before_hook <command> <function_name>"
        return 1
    fi

    _VIBE_HOOK_COUNTER+=1
    local hook_id="before_${command}_${_VIBE_HOOK_COUNTER}"
    _VIBE_BEFORE_HOOKS[$hook_id]="$hook_func"

    # Export for subshells
    typeset -gx _VIBE_BEFORE_HOOKS
}

# Registers an after hook for a command
# Usage: vibe_register_after_hook <command> <function_name>
vibe_register_after_hook() {
    local command="$1"
    local hook_func="$2"

    if [[ -z "$command" || -z "$hook_func" ]]; then
        log_error "Usage: vibe_register_after_hook <command> <function_name>"
        return 1
    fi

    _VIBE_HOOK_COUNTER+=1
    local hook_id="after_${command}_${_VIBE_HOOK_COUNTER}"
    _VIBE_AFTER_HOOKS[$hook_id]="$hook_func"

    # Export for subshells
    typeset -gx _VIBE_AFTER_HOOKS
}

# ── Hook Execution ────────────────────────────────────────
# Executes before hooks for a command in registration order
# Usage: _vibe_execute_before_hooks <command> [args...]
_vibe_execute_before_hooks() {
    local command="$1"
    shift

    # Get hook IDs sorted by registration order (embedded in ID)
    local -a hook_ids
    hook_ids=(${(k)_VIBE_BEFORE_HOOKS})
    hook_ids=(${(on)hook_ids})  # Sort numerically

    for hook_id in "${hook_ids[@]}"; do
        if [[ "$hook_id" == before_${command}_* ]]; then
            local hook_func="${_VIBE_BEFORE_HOOKS[$hook_id]}"
            if typeset -f "$hook_func" > /dev/null; then
                "$hook_func" "$@" || {
                    log_error "Before hook '$hook_func' failed for command '$command'"
                    return 1
                }
            fi
        fi
    done

    return 0
}

# Executes after hooks for a command in registration order
# Usage: _vibe_execute_after_hooks <command> <exit_code> [args...]
_vibe_execute_after_hooks() {
    local command="$1"
    local exit_code="$2"
    shift 2

    # Get hook IDs sorted by registration order (embedded in ID)
    local -a hook_ids
    hook_ids=(${(k)_VIBE_AFTER_HOOKS})
    hook_ids=(${(on)hook_ids})  # Sort numerically

    for hook_id in "${hook_ids[@]}"; do
        if [[ "$hook_id" == after_${command}_* ]]; then
            local hook_func="${_VIBE_AFTER_HOOKS[$hook_id]}"
            if typeset -f "$hook_func" > /dev/null; then
                "$hook_func" "$exit_code" "$@" || {
                    log_error "After hook '$hook_func' failed for command '$command'"
                    # Continue executing other hooks even if one fails
                }
            fi
        fi
    done
}

# ── Command Execution with Lifecycle ──────────────────────
# Executes a command with full lifecycle management
# Usage: vibe_execute_with_lifecycle <command> [args...]
vibe_execute_with_lifecycle() {
    local command="$1"
    shift

    local exit_code=0

    # Execute before hooks
    _vibe_execute_before_hooks "$command" "$@" || {
        log_error "Before hooks failed for command '$command'"
        return 1
    }

    # Execute the command
    "$@"
    exit_code=$?

    # Execute after hooks (always, even if command failed)
    _vibe_execute_after_hooks "$command" "$exit_code"

    return $exit_code
}

# ── Lifecycle Initialization ──────────────────────────────
# Initializes lifecycle system for a capability
# Usage: vibe_init_lifecycle <capability_name>
vibe_init_lifecycle() {
    local capability="$1"

    # Call capability's hook registration function if it exists
    local register_func="vibe_${capability}_register_hooks"
    if typeset -f "$register_func" > /dev/null; then
        "$register_func"
    fi
}

# ── Hook Discovery ────────────────────────────────────────
# Discovers and registers hooks from capability modules
# Usage: vibe_discover_hooks
vibe_discover_hooks() {
    local cap_dir="$VIBE_ROOT/lib/capabilities"

    if [[ -d "$cap_dir" ]]; then
        for cap_file in "$cap_dir"/*.sh(N); do
            local cap_name="${cap_file:t:r}"

            # Initialize lifecycle for each capability
            vibe_init_lifecycle "$cap_name"
        done
    fi
}

# ── Hook Status ───────────────────────────────────────────
# Shows registered hooks for debugging
# Usage: vibe_show_hooks
vibe_show_hooks() {
    echo "Before Hooks:"
    for hook_id hook_func in ${(kv)_VIBE_BEFORE_HOOKS}; do
        echo "  $hook_id -> $hook_func"
    done

    echo ""
    echo "After Hooks:"
    for hook_id hook_func in ${(kv)_VIBE_AFTER_HOOKS}; do
        echo "  $hook_id -> $hook_func"
    done
}
