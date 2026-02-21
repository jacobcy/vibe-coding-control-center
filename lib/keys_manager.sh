#!/usr/bin/env zsh
# lib/keys_manager.sh
# Key group management library for Vibe environment

# Resolve script directory for sourcing dependencies
_keys_manager_dir="$(cd "$(dirname "${(%):-%x}")" && pwd)"

# Source dependencies
if [[ -f "${_keys_manager_dir}/utils.sh" ]]; then
    source "${_keys_manager_dir}/utils.sh"
fi
if [[ -f "${_keys_manager_dir}/config.sh" ]]; then
    source "${_keys_manager_dir}/config.sh"
fi

# Keys directory location
VIBE_KEYS_DIR="${VIBE_HOME:-$HOME/.vibe}/keys"

# List all available key groups
# Usage: vibe_keys_list
vibe_keys_list() {
    local found=0

    echo "Available key groups:"

    if [[ ! -d "$VIBE_KEYS_DIR" ]]; then
        log_warn "Keys directory not found: $VIBE_KEYS_DIR"
        return 1
    fi

    for f in "$VIBE_KEYS_DIR"/*.env(N); do
        [[ -f "$f" ]] || continue
        local name=$(basename "$f" .env)

        # Skip the 'current' symlink
        [[ "$name" == "current" ]] && continue

        # Check if this is the current group
        local marker=""
        if [[ -L "$VIBE_KEYS_DIR/current" ]]; then
            local target=$(readlink "$VIBE_KEYS_DIR/current" 2>/dev/null)
            if [[ "$target" == "${name}.env" ]]; then
                marker=" (current)"
            fi
        fi

        echo "  $name$marker"
        found=1
    done

    if [[ $found -eq 0 ]]; then
        echo "  No key groups found"
        echo ""
        log_info "Create a key group with: vibe keys create <name>"
    fi
}

# Switch to a different key group
# Usage: vibe_keys_use <group_name>
vibe_keys_use() {
    local group="$1"

    if [[ -z "$group" ]]; then
        log_error "Key group name required"
        echo "Usage: vibe keys use <group-name>"
        echo ""
        echo "Available groups:"
        vibe_keys_list
        return 1
    fi

    local target="$VIBE_KEYS_DIR/${group}.env"

    if [[ ! -f "$target" ]]; then
        log_error "Key group not found: $group"
        echo ""
        log_info "Available groups:"
        vibe_keys_list
        return 1
    fi

    # Update the symlink
    rm -f "$VIBE_KEYS_DIR/current"
    ln -s "${group}.env" "$VIBE_KEYS_DIR/current"

    # Update vibe.yaml if it exists
    if type set_current_keys_group >/dev/null 2>&1; then
        set_current_keys_group "$group" 2>/dev/null
    fi

    log_success "Switched to key group: $group"
}

# Show the current key group
# Usage: vibe_keys_current
vibe_keys_current() {
    local current
    current=$(get_current_keys_group 2>/dev/null || echo "unknown")

    echo "Current key group: $current"

    # Show the actual file path
    local keys_file="$VIBE_KEYS_DIR/${current}.env"
    if [[ -f "$keys_file" ]]; then
        echo "File: $keys_file"
    fi
}

# Set a key value in the current key group
# Usage: vibe_keys_set <KEY=value>
vibe_keys_set() {
    local key_value="$1"

    if [[ -z "$key_value" ]]; then
        log_error "Key=value required"
        echo "Usage: vibe keys set KEY=value"
        echo "Example: vibe keys set ANTHROPIC_AUTH_TOKEN=sk-ant-..."
        return 1
    fi

    # Validate format
    if [[ ! "$key_value" =~ ^([A-Z_][A-Z0-9_]*)=(.*)$ ]]; then
        log_error "Invalid format. Use KEY=value (KEY must be uppercase letters, numbers, and underscores)"
        return 1
    fi

    local key="${match[1]}"
    local value="${match[2]}"

    local current_group
    current_group=$(get_current_keys_group 2>/dev/null || echo "anthropic")
    local keys_file="$VIBE_KEYS_DIR/${current_group}.env"

    # Create the file if it doesn't exist
    if [[ ! -f "$keys_file" ]]; then
        mkdir -p "$(dirname "$keys_file")"
        touch "$keys_file"
    fi

    # Check if key already exists
    if grep -q "^${key}=" "$keys_file" 2>/dev/null; then
        # Update existing key (macOS sed compatible)
        if sed --version 2>/dev/null | grep -q GNU; then
            sed -i "s|^${key}=.*|${key}=${value}|" "$keys_file"
        else
            sed -i '' "s|^${key}=.*|${key}=${value}|" "$keys_file"
        fi
        log_success "Updated $key in group: $current_group"
    else
        # Add new key
        echo "${key}=${value}" >> "$keys_file"
        log_success "Added $key to group: $current_group"
    fi
}

# Get a key value from the current key group
# Usage: vibe_keys_get <KEY>
vibe_keys_get() {
    local key="$1"

    if [[ -z "$key" ]]; then
        log_error "Key name required"
        echo "Usage: vibe keys get <KEY>"
        return 1
    fi

    local current_group
    current_group=$(get_current_keys_group 2>/dev/null || echo "anthropic")
    local keys_file="$VIBE_KEYS_DIR/${current_group}.env"

    if [[ ! -f "$keys_file" ]]; then
        log_error "Keys file not found: $keys_file"
        return 1
    fi

    # Extract value
    local value
    value=$(grep "^${key}=" "$keys_file" 2>/dev/null | head -1 | cut -d'=' -f2-)

    if [[ -n "$value" ]]; then
        echo "$value"
    else
        log_warn "Key not found: $key"
        return 1
    fi
}

# Create a new key group
# Usage: vibe_keys_create <group_name>
vibe_keys_create() {
    local group="$1"

    if [[ -z "$group" ]]; then
        log_error "Key group name required"
        echo "Usage: vibe keys create <group-name>"
        return 1
    fi

    # Validate group name (lowercase letters, numbers, hyphens)
    if [[ ! "$group" =~ ^[a-z][a-z0-9-]*$ ]]; then
        log_error "Invalid group name. Use lowercase letters, numbers, and hyphens"
        return 1
    fi

    local target="$VIBE_KEYS_DIR/${group}.env"

    if [[ -f "$target" ]]; then
        log_error "Key group already exists: $group"
        return 1
    fi

    mkdir -p "$VIBE_KEYS_DIR"

    # Create with template based on provider type
    case "$group" in
        anthropic*)
            cat > "$target" << 'EOF'
# Anthropic API Keys
ANTHROPIC_AUTH_TOKEN=
ANTHROPIC_BASE_URL=https://api.anthropic.com
ANTHROPIC_MODEL=claude-sonnet-4-5
EOF
            ;;
        openai*)
            cat > "$target" << 'EOF'
# OpenAI API Keys
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com
EOF
            ;;
        deepseek*)
            cat > "$target" << 'EOF'
# DeepSeek API Keys
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
EOF
            ;;
        *)
            cat > "$target" << 'EOF'
# API Keys
# Add your keys here in KEY=VALUE format
EOF
            ;;
    esac

    log_success "Created key group: $group"
    echo "File: $target"
    echo ""
    log_info "Edit with: vibe keys edit $group"
}

# Edit a key group file
# Usage: vibe_keys_edit [group_name]
vibe_keys_edit() {
    local group="$1"

    if [[ -z "$group" ]]; then
        group=$(get_current_keys_group 2>/dev/null || echo "anthropic")
    fi

    local keys_file="$VIBE_KEYS_DIR/${group}.env"

    if [[ ! -f "$keys_file" ]]; then
        log_error "Key group not found: $group"
        return 1
    fi

    # Use open_editor if available, otherwise use $EDITOR
    if type open_editor >/dev/null 2>&1; then
        open_editor "$keys_file"
    else
        local editor="${EDITOR:-vim}"
        "$editor" "$keys_file"
    fi
}

# Delete a key group
# Usage: vibe_keys_delete <group_name>
vibe_keys_delete() {
    local group="$1"

    if [[ -z "$group" ]]; then
        log_error "Key group name required"
        echo "Usage: vibe keys delete <group-name>"
        return 1
    fi

    local target="$VIBE_KEYS_DIR/${group}.env"

    if [[ ! -f "$target" ]]; then
        log_error "Key group not found: $group"
        return 1
    fi

    # Don't delete if it's the current group
    local current_group
    current_group=$(get_current_keys_group 2>/dev/null || echo "")
    if [[ "$group" == "$current_group" ]]; then
        log_error "Cannot delete the current key group"
        log_info "Switch to another group first: vibe keys use <other-group>"
        return 1
    fi

    rm -f "$target"
    log_success "Deleted key group: $group"
}
