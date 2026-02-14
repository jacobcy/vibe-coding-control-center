#!/usr/bin/env zsh
# Enhanced configuration loader with security, caching, and validation
# Implements secure configuration loading with centralized validation

# Source the utility functions for logging and validation
# Calculate script directory using parameter expansion to avoid issues with dirname
local_script_dir="${(%):-%x}"  # Get current script path
local_utils_dir="${local_script_dir%/*}"  # Get directory (equivalent to dirname)
source "$local_utils_dir/utils.sh"

# Configuration cache
declare -A CONFIG_CACHE
CONFIG_LOADED=false
CACHE_TIMESTAMP=0
CACHE_TTL=300  # 5 minutes

load_configuration() {
    local force_refresh=${1:-false}

    # Check if we have a valid cache
    if [[ $CONFIG_LOADED == true && $force_refresh == false ]]; then
        local current_time=$(date +%s)
        local time_diff=$((current_time - CACHE_TIMESTAMP))

        if [[ $time_diff -lt $CACHE_TTL ]]; then
            return 0  # Return cached config
        fi
    fi

    # Load from file with security validation
    local config_file="$HOME/.vibe/keys.env"
    if [[ -f "$config_file" ]]; then
        validate_and_load_config "$config_file"
    else
        # Fallback to default location
        config_file="./config/keys.env"
        if [[ -f "$config_file" ]]; then
            validate_and_load_config "$config_file"
        fi
    fi

    # Additionally, try to load project-level configuration if available
    local project_config_file=""
    # Check current directory for .vibe
    if [[ -d "$PWD/.vibe" ]]; then
        project_config_file="$PWD/.vibe/keys.env"
    # Check git root
    elif git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        local git_root
        git_root="$(git rev-parse --show-toplevel 2>/dev/null)"
        if [[ -d "$git_root/.vibe" ]]; then
            project_config_file="$git_root/.vibe/keys.env"
        fi
    fi

    # Load project-level config if available (overrides global config)
    if [[ -n "$project_config_file" && -f "$project_config_file" ]]; then
        validate_and_load_config "$project_config_file"
    fi

    # Mark cache as loaded
    CONFIG_LOADED=true
    CACHE_TIMESTAMP=$(date +%s)
}

validate_and_load_config() {
    local config_path="$1"

    # Validate path security
    if ! validate_secure_path "$config_path"; then
        log_error "Invalid configuration path: $config_path"
        return 1
    fi

    # Check file permissions (should not be world-writable)
    local perms
    if command -v stat >/dev/null 2>&1; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS stat format
            perms=$(stat -f %OLp "$config_path" 2>/dev/null)
        else
            # Linux stat format
            perms=$(stat -c %a "$config_path" 2>/dev/null)
        fi
    fi

    if [[ -n "$perms" && "${perms: -1}" -gt 6 ]]; then
        log_warn "Configuration file has loose permissions: $config_path"
    fi

    # Source the configuration safely
    local temp_vars=$(mktemp)
    trap "rm -f '$temp_vars'" EXIT

    # Read the config file line by line and export variables to temp file for validation
    local line
    while IFS= read -r line || [[ -n "$line" ]]; do
        # Skip comments and empty lines
        [[ "$line" =~ ^[[:space:]]*# ]] && continue
        [[ -z "${line//[[:space:]]/}" ]] && continue

        # Validate that the line is a valid assignment
        if [[ "$line" =~ ^[A-Z_][A-Z0-9_]*= ]]; then
            echo "$line" >> "$temp_vars"
        fi
    done < "$config_path"

    # Source validated variables
    source "$temp_vars"

    # Store in cache by reading from the validated temp file
    while IFS= read -r line || [[ -n "$line" ]]; do
        # Skip comments and empty lines
        [[ "$line" =~ ^[[:space:]]*# ]] && continue
        [[ -z "${line//[[:space:]]/}" ]] && continue

        # Parse key=value pairs
        if [[ "$line" =~ ^([A-Z_][A-Z0-9_]*)=(.*) ]]; then
            local key="${match[1]}"
            local value="${match[2]}"
            # Remove quotes if present
            value="${value#\"}"
            value="${value%\"}"
            value="${value#\'}"
            value="${value%\'}"
            CONFIG_CACHE[$key]="$value"
        fi
    done < "$temp_vars"
}


get_config_value() {
    local key="$1"
    local default_value="${2:-}"

    # Load config if not already loaded
    load_configuration

    # Check if key exists in cache
    if (( ${+CONFIG_CACHE[$key]} )); then
        echo "${CONFIG_CACHE[$key]}"
    else
        # Skip trying to get from environment variable to avoid complex indirection issues
        # Users can access environment variables directly if needed
        echo "$default_value"
    fi
}

get_secret_value() {
    local key="$1"
    local default_value="${2:-}"

    # Same as get_config_value but logs differently for sensitive data
    local value=$(get_config_value "$key" "$default_value")
    if [[ -n "$value" && "$value" != "$default_value" ]]; then
        log_debug "Retrieved secret: $key"
    fi
    echo "$value"
}

# Refresh the configuration cache
refresh_config_cache() {
    load_configuration true
}

# Clear the configuration cache
clear_config_cache() {
    # In zsh, to clear an associative array, we need to unset it and redeclare it
    unset CONFIG_CACHE
    typeset -gA CONFIG_CACHE
    CONFIG_LOADED=false
    CACHE_TIMESTAMP=0
    log_info "Configuration cache cleared"
}

# Validate that configuration has required values
validate_required_config() {
    local required_keys=("$@")
    local missing_keys=()

    for key in "${required_keys[@]}"; do
        local value=$(get_config_value "$key")
        if [[ -z "$value" ]]; then
            missing_keys+=("$key")
        fi
    done

    if [[ ${#missing_keys[@]} -gt 0 ]]; then
        log_error "Missing required configuration values: ${missing_keys[*]}"
        return 1
    fi

    return 0
}