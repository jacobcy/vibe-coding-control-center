#!/usr/bin/env zsh
# lib/config_init.sh
# Shared configuration initialization logic
# Used by: install.sh, vibe-env, vibe-config

# Get VIBE_ROOT dynamically
get_vibe_root() {
    local script_dir="$(cd "$(dirname "${(%):-%x}")" && pwd)"
    if [[ -d "$script_dir/../bin" ]]; then
        # Called from lib/
        echo "$(cd "$script_dir/.." && pwd)"
    elif [[ -d "$script_dir/bin" ]]; then
        # Called from project root
        echo "$script_dir"
    else
        # Fallback: search upward
        local current="$script_dir"
        while [[ "$current" != "/" ]]; do
            if [[ -d "$current/bin" && -d "$current/lib" ]]; then
                echo "$current"
                return 0
            fi
            current="$(dirname "$current")"
        done
        echo "$script_dir"
    fi
}

# Sync project keys.env to user directory
# Usage: sync_keys_env [vibe_root_path]
sync_keys_env() {
    local vibe_root="${1:-$(get_vibe_root)}"
    local vibe_home="$VIBE_HOME"
    local keys_file="$vibe_home/keys.env"
    local project_keys="$vibe_root/config/keys.env"
    local template_keys="$vibe_root/config/keys.template.env"
    
    # Ensure VIBE_HOME exists
    mkdir -p "$vibe_home"
    
    # Check if project has real keys.env
    if [[ ! -f "$project_keys" ]]; then
        log_error "Project keys.env not found: $project_keys"
        echo ""
        echo "${BOLD}Please create your configuration:${NC}"
        echo "  1. Copy the template:"
        echo "     ${CYAN}cp $template_keys $project_keys${NC}"
        echo ""
        echo "  2. Edit and fill in your API keys:"
        echo "     ${CYAN}\${EDITOR:-vim} $project_keys${NC}"
        echo ""
        echo "  3. Then run sync again: ${CYAN}vibe env sync${NC}"
        echo ""
        return 1
    fi
    
    # If keys.env already exists in user directory, ask if user wants to overwrite
    if [[ -f "$keys_file" ]]; then
        log_info "Configuration file already exists: $keys_file"
        
        if confirm_action "Overwrite with project's keys.env?" "n"; then
            cp "$project_keys" "$keys_file"
            chmod 600 "$keys_file"
            log_success "Synced project config to $keys_file"
            return 0
        else
            log_info "Keeping existing configuration"
            return 0
        fi
    fi
    
    # Copy project keys.env to user directory
    cp "$project_keys" "$keys_file"
    chmod 600 "$keys_file"
    log_success "Synced project config to $keys_file"
    return 0
}

# Verify keys.env has real values (not just template placeholders)
verify_keys_configured() {
    local keys_file="${1:-$VIBE_HOME/keys.env}"
    
    [[ -f "$keys_file" ]] || {
        log_warn "keys.env not found at $keys_file"
        return 1
    }
    
    # Check for template placeholders
    local has_real_keys=0
    while IFS= read -r line || [[ -n "$line" ]]; do
        # Skip comments and empty lines
        [[ "$line" =~ ^[[:space:]]*# ]] && continue
        [[ -z "${line//[[:space:]]/}" ]] && continue
        
        # Check if it's a key=value pair
        if [[ "$line" =~ ^([^=]+)=(.*)$ ]]; then
            local key="${match[1]}"
            local val="${match[2]}"
            
            # Remove quotes
            val="${val%\"}"
            val="${val#\"}"
            
            # Check if it's NOT a template value
            if [[ -n "$val" && "$val" != *"xxxx"* && "$val" != *"xxxxxxxx"* ]]; then
                has_real_keys=1
                break
            fi
        fi
    done < "$keys_file"
    
    return $((1 - has_real_keys))
}

# Helper: Get a value from keys.env
get_env_value() {
    local key="$1"
    local keys_file="${2:-$VIBE_HOME/keys.env}"
    
    [[ -f "$keys_file" ]] || return 1
    
    grep -E "^[[:space:]]*$key=" "$keys_file" 2>/dev/null | \
        head -1 | \
        cut -d= -f2- | \
        sed 's/^"//;s/"$//'
}

# Helper: Set a value in keys.env
set_env_value() {
    local key="$1"
    local value="$2"
    local keys_file="${3:-$VIBE_HOME/keys.env}"
    
    [[ -f "$keys_file" ]] || {
        log_error "keys.env not found at $keys_file"
        return 1
    }
    
    local temp_file=$(mktemp)
    
    # Remove existing key if present
    grep -vE "^[[:space:]]*$key=" "$keys_file" > "$temp_file" 2>/dev/null || true
    
    # Add new key=value
    echo "$key=\"$value\"" >> "$temp_file"
    
    # Securely write back
    if secure_write_file "$keys_file" "$(cat "$temp_file")" "600"; then
        rm -f "$temp_file"
        return 0
    else
        rm -f "$temp_file"
        return 1
    fi
}
