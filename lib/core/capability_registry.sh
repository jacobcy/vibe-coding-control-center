#!/usr/bin/env zsh
# v3/lib/core/capability_registry.sh - Capability Registry
# Manages capability registration, discovery, and invocation

# Registry State
typeset -A _VIBE_CAPABILITY_REGISTRY
typeset -A _VIBE_CAPABILITY_METADATA
typeset -A _VIBE_CAPABILITY_DEPS

# Registers a capability with metadata
# Usage: vibe_register_capability <name> [version] [description]
vibe_register_capability() {
    local name="$1"
    local version="${2:-1.0.0}"
    local description="${3:-}"

    if [[ -z "$name" ]]; then
        log_error "Usage: vibe_register_capability <name> [version] [description]"
        return 1
    fi

    # Check for duplicate registration
    if [[ -n "${_VIBE_CAPABILITY_REGISTRY[$name]:-}" ]]; then
        log_warn "Capability '$name' already registered, skipping"
        return 0
    fi

    # Store capability metadata
    _VIBE_CAPABILITY_REGISTRY[$name]="registered"
    _VIBE_CAPABILITY_METADATA[$name]="version=$version|description=$description"

    log_debug "Registered capability: $name (v$version)"
}

# Discovers capabilities by scanning lib/capabilities/
# Usage: vibe_discover_capabilities
vibe_discover_capabilities() {
    local cap_dir="$VIBE_ROOT/lib/capabilities"

    if [[ ! -d "$cap_dir" ]]; then
        log_warning "Capabilities directory not found: $cap_dir"
        return 0
    fi

    # Scan for capability modules
    for cap_file in "$cap_dir"/*.sh(N); do
        local cap_name="${cap_file:t:r}"

        # Source the capability to trigger registration
        source "$cap_file"

        # Call capability's init function if it exists
        local init_func="vibe_${cap_name}_init"
        if typeset -f "$init_func" > /dev/null; then
            "$init_func"
        fi
    done
}

# Looks up a capability by name
# Usage: vibe_lookup_capability <name>
# Returns: 0 if found, 1 if not found
vibe_lookup_capability() {
    local name="$1"

    if [[ -z "$name" ]]; then
        log_error "Usage: vibe_lookup_capability <name>"
        return 1
    fi

    if [[ -n "${_VIBE_CAPABILITY_REGISTRY[$name]:-}" ]]; then
        return 0
    else
        return 1
    fi
}

# Gets metadata for a capability
# Usage: vibe_get_capability_metadata <name>
# Returns: metadata string (version=...|description=...)
vibe_get_capability_metadata() {
    local name="$1"

    if [[ -z "$name" ]]; then
        log_error "Usage: vibe_get_capability_metadata <name>"
        return 1
    fi

    echo "${_VIBE_CAPABILITY_METADATA[$name]:-}"
}

# Invokes a capability with arguments
# Usage: vibe_invoke_capability <name> [args...]
vibe_invoke_capability() {
    local name="$1"
    shift

    if [[ -z "$name" ]]; then
        log_error "Usage: vibe_invoke_capability <name> [args...]"
        return 1
    fi

    # Check if capability is registered
    if ! vibe_lookup_capability "$name"; then
        log_error "Capability not found: $name"
        return 1
    fi

    # Load the capability module
    local cap_file="$VIBE_ROOT/lib/capabilities/${name}.sh"
    if [[ ! -f "$cap_file" ]]; then
        log_error "Capability file not found: $cap_file"
        return 1
    fi

    source "$cap_file"

    # Call the capability's main function
    local func_name="vibe_${name}"
    if typeset -f "$func_name" > /dev/null; then
        "$func_name" "$@"
    else
        log_error "Capability '$name' loaded but function '$func_name' not found"
        return 1
    fi
}

# Declares dependencies for a capability
# Usage: vibe_declare_deps <capability> <dep1> [dep2] ...
vibe_declare_deps() {
    local capability="$1"
    shift

    if [[ -z "$capability" ]]; then
        log_error "Usage: vibe_declare_deps <capability> <dep1> [dep2] ..."
        return 1
    fi

    _VIBE_CAPABILITY_DEPS[$capability]="${(j:,:)@}"
}

# Resolves dependencies for a capability
# Usage: vibe_resolve_deps <capability>
# Returns: 0 if all deps satisfied, 1 otherwise
vibe_resolve_deps() {
    local capability="$1"

    if [[ -z "$capability" ]]; then
        log_error "Usage: vibe_resolve_deps <capability>"
        return 1
    fi

    local deps="${_VIBE_CAPABILITY_DEPS[$capability]:-}"

    if [[ -z "$deps" ]]; then
        # No dependencies declared
        return 0
    fi

    # Check each dependency
    local -a dep_list
    IFS=',' read -rA dep_list <<< "$deps"

    for dep in "${dep_list[@]}"; do
        if ! vibe_lookup_capability "$dep"; then
            log_error "Capability '$capability' depends on '$dep', which is not registered"
            return 1
        fi
    done

    return 0
}

# Shows all registered capabilities
# Usage: vibe_show_registry
vibe_show_registry() {
    echo "Registered Capabilities:"
    echo ""

    for cap_name capability_status in ${(kv)_VIBE_CAPABILITY_REGISTRY}; do
        local metadata="${_VIBE_CAPABILITY_METADATA[$cap_name]}"
        local deps="${_VIBE_CAPABILITY_DEPS[$cap_name]:-none}"

        echo "  ${GREEN}${cap_name}${NC}"
        echo "    Metadata: $metadata"
        echo "    Dependencies: $deps"
    done
}

# Initializes the capability registry
# Usage: vibe_init_registry
vibe_init_registry() {
    # Clear existing state
    _VIBE_CAPABILITY_REGISTRY=()
    _VIBE_CAPABILITY_METADATA=()
    _VIBE_CAPABILITY_DEPS=()

    # Discover and register all capabilities
    vibe_discover_capabilities
}
