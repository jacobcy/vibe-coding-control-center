#!/usr/bin/env zsh
# Plugin System for Vibe Coding Control Center

# Declare associative arrays for plugin management
declare -A PLUGINS
declare -a PLUGIN_LOAD_ORDER

# Initialize plugin manager
initialize_plugin_system() {
    log_info "Initializing plugin system..."
}

# Register a plugin
register_plugin() {
    local plugin_name="$1"
    local plugin_path="$2"
    local plugin_version="${3:-1.0.0}"

    # Validate inputs
    if ! validate_input "$plugin_name" "false"; then
        log_error "Invalid plugin name: $plugin_name"
        return 1
    fi

    if ! validate_path "$plugin_path" "Plugin path validation failed"; then
        log_error "Invalid plugin path: $plugin_path"
        return 1
    fi

    # Store plugin info
    PLUGINS["$plugin_name.path"]="$plugin_path"
    PLUGINS["$plugin_name.version"]="$plugin_version"
    PLUGINS["$plugin_name.loaded"]="false"

    # Add to load order
    PLUGIN_LOAD_ORDER+=("$plugin_name")

    log_info "Registered plugin: $plugin_name (v$plugin_version)"
}

# Load a specific plugin
load_plugin() {
    local plugin_name="$1"

    if [[ -z "${PLUGINS[$plugin_name.path]+isset}" ]]; then
        log_error "Plugin not registered: $plugin_name"
        return 1
    fi

    local plugin_path="${PLUGINS[$plugin_name.path]}"

    if [[ ! -f "$plugin_path" ]]; then
        log_error "Plugin file does not exist: $plugin_path"
        return 1
    fi

    # Validate the plugin file before sourcing
    if ! validate_path "$plugin_path" "Plugin file validation failed"; then
        log_error "Invalid plugin file path: $plugin_path"
        return 1
    fi

    # Source the plugin
    source "$plugin_path"

    # Mark as loaded
    PLUGINS["$plugin_name.loaded"]="true"
    log_info "Loaded plugin: $plugin_name"

    # Execute plugin init function if available
    if declare -f "${plugin_name}_init" >/dev/null; then
        "${plugin_name}_init"
    fi
}

# Load all registered plugins
load_all_plugins() {
    for plugin_name in "${PLUGIN_LOAD_ORDER[@]}"; do
        if [[ "${PLUGINS[$plugin_name.loaded]}" == "false" ]]; then
            load_plugin "$plugin_name"
        fi
    done
}

# Check if a plugin is loaded
is_plugin_loaded() {
    local plugin_name="$1"
    [[ "${PLUGINS[$plugin_name.loaded]}" == "true" ]]
}

# Get plugin info
get_plugin_info() {
    local plugin_name="$1"
    local info_type="$2"  # path, version, loaded

    echo "${PLUGINS[$plugin_name.$info_type]}"
}

# List all registered plugins
list_plugins() {
    echo "Registered Plugins:"
    for plugin_name in "${PLUGIN_LOAD_ORDER[@]}"; do
        local version="${PLUGINS[$plugin_name.version]}"
        local loaded="${PLUGINS[$plugin_name.loaded]}"
        local path="${PLUGINS[$plugin_name.path]}"
        echo "  - $plugin_name (v$version) [$loaded] - $path"
    done
}

# Initialize the plugin system
initialize_plugin_system