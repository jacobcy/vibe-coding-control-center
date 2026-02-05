#!/bin/bash
# Cache System for Vibe Coding Control Center

# Default cache directory
DEFAULT_CACHE_DIR="$HOME/.vibe-cache"

# Initialize cache system
initialize_cache() {
    local cache_dir="${1:-$DEFAULT_CACHE_DIR}"

    # Validate cache directory path
    if ! validate_path "$cache_dir" "Cache directory path validation failed"; then
        log_error "Invalid cache directory: $cache_dir"
        return 1
    fi

    # Create cache directory if it doesn't exist
    if ! mkdir -p "$cache_dir" 2>/dev/null; then
        log_error "Cannot create cache directory: $cache_dir"
        return 1
    fi

    CACHE_DIR="$cache_dir"
    export CACHE_DIR
    log_debug "Cache system initialized at: $CACHE_DIR"
}

# Cache a value with TTL
cache_set() {
    local key="$1"
    local value="$2"
    local ttl="${3:-3600}"  # Default 1 hour TTL in seconds

    # Validate inputs
    if ! validate_input "$key" "false"; then
        log_error "Invalid cache key: $key"
        return 1
    fi

    if ! validate_input "$value" "true"; then
        log_error "Invalid cache value for key: $key"
        return 1
    fi

    if ! [[ "$ttl" =~ ^[0-9]+$ ]] || [[ "$ttl" -lt 1 ]]; then
        log_error "Invalid TTL value: $ttl"
        return 1
    fi

    # Create cache entry with expiration
    local cache_file="$CACHE_DIR/${key}.json"
    local temp_file
    temp_file=$(mktemp) || {
        log_error "Failed to create temporary cache file"
        return 1
    }

    local now
    now=$(date +%s)
    local expires=$((now + ttl))

    # Create JSON content
    printf '{"value":"%s","expires":%d,"created":%d}' "$value" "$expires" "$now" > "$temp_file"

    # Atomically move to final location
    mv "$temp_file" "$cache_file" || {
        log_error "Failed to write cache file: $cache_file"
        rm -f "$temp_file" 2>/dev/null
        return 1
    }

    log_debug "Cached key '$key' with TTL $ttl seconds"
}

# Retrieve a cached value
cache_get() {
    local key="$1"

    # Validate input
    if ! validate_input "$key" "false"; then
        log_error "Invalid cache key: $key"
        return 1
    fi

    local cache_file="$CACHE_DIR/${key}.json"

    # Check if cache file exists
    if [[ ! -f "$cache_file" ]]; then
        log_debug "Cache miss for key: $key"
        return 1
    fi

    # Check if cache entry is expired
    local now
    now=$(date +%s)
    local expires
    expires=$(jq -r '.expires' "$cache_file" 2>/dev/null)

    if [[ $? -ne 0 ]] || [[ -z "$expires" ]] || [[ "$now" -ge "$expires" ]]; then
        # Entry is expired or corrupted
        rm -f "$cache_file" 2>/dev/null
        log_debug "Cache expired for key: $key"
        return 1
    fi

    # Return cached value
    local value
    value=$(jq -r '.value' "$cache_file" 2>/dev/null)
    if [[ $? -eq 0 ]] && [[ -n "$value" ]] && [[ "$value" != "null" ]]; then
        echo "$value"
        log_debug "Cache hit for key: $key"
        return 0
    else
        # Corrupted cache file
        rm -f "$cache_file" 2>/dev/null
        log_debug "Corrupted cache for key: $key"
        return 1
    fi
}

# Delete a cached value
cache_delete() {
    local key="$1"

    # Validate input
    if ! validate_input "$key" "false"; then
        log_error "Invalid cache key: $key"
        return 1
    fi

    local cache_file="$CACHE_DIR/${key}.json"
    if [[ -f "$cache_file" ]]; then
        rm -f "$cache_file" 2>/dev/null
        log_debug "Deleted cache entry for key: $key"
    fi
}

# Clear all cache
cache_clear() {
    if [[ -d "$CACHE_DIR" ]]; then
        rm -rf "$CACHE_DIR"/*
        log_info "Cleared cache directory: $CACHE_DIR"
    fi
}

# Get cache statistics
cache_stats() {
    if [[ -d "$CACHE_DIR" ]]; then
        local total_files
        total_files=$(find "$CACHE_DIR" -name "*.json" 2>/dev/null | wc -l | tr -d ' ')

        local expired_files=0
        local now
        now=$(date +%s)

        # Count expired files
        while IFS= read -r -d '' file; do
            local expires
            expires=$(jq -r '.expires' "$file" 2>/dev/null)
            if [[ -n "$expires" ]] && [[ "$now" -ge "$expires" ]]; then
                ((expired_files++))
            fi
        done < <(find "$CACHE_DIR" -name "*.json" -print0 2>/dev/null)

        local valid_files=$((total_files - expired_files))

        echo "Cache Statistics:"
        echo "  Total files: $total_files"
        echo "  Valid files: $valid_files"
        echo "  Expired files: $expired_files"
        echo "  Cache directory: $CACHE_DIR"
    else
        echo "Cache directory does not exist: $CACHE_DIR"
    fi
}

# Cleanup expired entries
cache_cleanup_expired() {
    if [[ -d "$CACHE_DIR" ]]; then
        local now
        now=$(date +%s)

        # Find and remove expired files
        while IFS= read -r -d '' file; do
            local expires
            expires=$(jq -r '.expires' "$file" 2>/dev/null)
            if [[ -n "$expires" ]] && [[ "$now" -ge "$expires" ]]; then
                rm -f "$file" 2>/dev/null
                log_debug "Removed expired cache file: $file"
            fi
        done < <(find "$CACHE_DIR" -name "*.json" -print0 2>/dev/null)

        log_info "Cache cleanup completed"
    fi
}

# Initialize cache system with default directory
initialize_cache