#!/usr/bin/env zsh
# lib/env_manager.sh
# Environment management library for Vibe environment

# Resolve script directory for sourcing dependencies
_env_manager_dir="$(cd "$(dirname "${(%):-%x}")" && pwd)"

# Source dependencies
if [[ -f "${_env_manager_dir}/utils.sh" ]]; then
    source "${_env_manager_dir}/utils.sh"
fi
if [[ -f "${_env_manager_dir}/config.sh" ]]; then
    source "${_env_manager_dir}/config.sh"
fi
if [[ -f "${_env_manager_dir}/vibe_dir_template.sh" ]]; then
    source "${_env_manager_dir}/vibe_dir_template.sh"
fi

# Initialize the Vibe environment
# Usage: vibe_env_init [--force]
vibe_env_init() {
    local force="${1:-}"

    log_step "Initializing Vibe environment..."

    local vibe_home="${VIBE_HOME:-$HOME/.vibe}"

    # Check if already initialized
    if [[ -d "$vibe_home" && -f "$vibe_home/vibe.yaml" && "$force" != "--force" ]]; then
        log_warn "Vibe environment already exists at: $vibe_home"
        log_info "Use 'vibe env init --force' to reinitialize"
        return 0
    fi

    # Create directory structure using template
    if type create_vibe_dir_structure >/dev/null 2>&1; then
        create_vibe_dir_structure "$vibe_home"
    else
        # Fallback: create basic structure
        mkdir -p "$vibe_home"/{keys,tools/claude,tools/opencode,mcp,skills,cache}
    fi

    log_success "Vibe environment initialized at: $vibe_home"
    echo ""
    echo "Next steps:"
    echo "  1. Edit $vibe_home/keys/anthropic.env and add your API key"
    echo "  2. Run 'vibe keys list' to see available key groups"
    echo "  3. Run 'vibe tool install claude' to install tools"
    echo "  4. Run 'vibe check' to verify your setup"
}

# Export the Vibe environment
# Usage: vibe_env_export [output_file]
# Default: outputs to stdout
vibe_env_export() {
    local output_file="${1:--}"
    local vibe_home="${VIBE_HOME:-$HOME/.vibe}"

    if [[ ! -d "$vibe_home" ]]; then
        log_error "Vibe environment not found at: $vibe_home"
        log_info "Run 'vibe env init' first"
        return 1
    fi

    if [[ "$output_file" == "-" ]]; then
        # Output to stdout (for copying)
        echo "# Vibe Environment Export"
        echo "# Generated: $(date)"
        echo ""

        # Export vibe.yaml
        if [[ -f "$vibe_home/vibe.yaml" ]]; then
            echo "# === vibe.yaml ==="
            cat "$vibe_home/vibe.yaml"
            echo ""
        fi

        # Export current keys (without values)
        local current_group
        current_group=$(get_current_keys_group 2>/dev/null || echo "anthropic")
        local keys_file="$vibe_home/keys/${current_group}.env"

        if [[ -f "$keys_file" ]]; then
            echo "# === keys/$current_group.env ==="
            # Mask actual key values
            while IFS= read -r line || [[ -n "$line" ]]; do
                if [[ "$line" =~ ^([A-Z_][A-Z0-9_]*)= ]]; then
                    echo "${match[1]}=<masked>"
                else
                    echo "$line"
                fi
            done < "$keys_file"
            echo ""
        fi

        # List tools
        echo "# === Tools ==="
        if [[ -d "$vibe_home/tools" ]]; then
            for tool_dir in "$vibe_home/tools"/*(N/); do
                local name=$(basename "$tool_dir")
                local enabled=$([[ -f "$tool_dir/enabled" ]] && echo "enabled" || echo "disabled")
                echo "  $name: $enabled"
            done
        fi
        echo ""

        # List skills
        echo "# === Skills ==="
        if [[ -d "$vibe_home/skills" ]]; then
            for skill_file in "$vibe_home/skills"/*.skill.yaml(N); do
                echo "  $(basename "$skill_file" .skill.yaml)"
            done
        fi

    else
        # Export to file (tarball)
        local tarball="${output_file%.tar.gz}.tar.gz"

        # Create tarball excluding sensitive key values
        local temp_dir="${TMPDIR:-/tmp}/vibe-export-$$"
        mkdir -p "$temp_dir"

        # Copy structure
        cp -r "$vibe_home"/* "$temp_dir/" 2>/dev/null || true

        # Mask key values
        for key_file in "$temp_dir/keys"/*.env(N); do
            if [[ -f "$key_file" ]]; then
                local masked_content=""
                while IFS= read -r line || [[ -n "$line" ]]; do
                    if [[ "$line" =~ ^([A-Z_][A-Z0-9_]*)= ]]; then
                        masked_content+="${match[1]}=<SET_YOUR_VALUE>\n"
                    else
                        masked_content+="${line}\n"
                    fi
                done < "$key_file"
                echo -e "$masked_content" > "$key_file"
            fi
        done

        # Create tarball
        tar -czf "$tarball" -C "$temp_dir" .

        # Cleanup
        rm -rf "$temp_dir"

        log_success "Exported to: $tarball"
        echo ""
        log_info "Key values have been masked for security"
        log_info "Edit the .env files after importing to set your keys"
    fi
}

# Import a Vibe environment
# Usage: vibe_env_import <tarball_file>
vibe_env_import() {
    local tarball="$1"
    local vibe_home="${VIBE_HOME:-$HOME/.vibe}"

    if [[ -z "$tarball" ]]; then
        log_error "Tarball file required"
        echo "Usage: vibe env import <tarball.tar.gz>"
        return 1
    fi

    if [[ ! -f "$tarball" ]]; then
        log_error "File not found: $tarball"
        return 1
    fi

    # Check if already initialized
    if [[ -d "$vibe_home" && -f "$vibe_home/vibe.yaml" ]]; then
        log_warn "Existing Vibe environment found at: $vibe_home"
        log_info "Backup existing environment first? (y/n)"
        read -r answer
        if [[ "$answer" == "y" || "$answer" == "Y" ]]; then
            local backup="$vibe_home.backup.$(date +%Y%m%d%H%M%S)"
            mv "$vibe_home" "$backup"
            log_info "Backup saved to: $backup"
        else
            log_error "Import cancelled"
            return 1
        fi
    fi

    # Extract tarball
    mkdir -p "$vibe_home"
    tar -xzf "$tarball" -C "$vibe_home"

    log_success "Imported environment to: $vibe_home"
    echo ""
    log_info "Remember to edit the .env files to set your API keys"
}

# Show environment status
# Usage: vibe_env_status
vibe_env_status() {
    local vibe_home="${VIBE_HOME:-$HOME/.vibe}"

    echo "Vibe Environment Status"
    echo "========================"
    echo ""

    # Check VIBE_HOME
    echo "Location: $vibe_home"

    if [[ ! -d "$vibe_home" ]]; then
        echo "Status: Not initialized"
        echo ""
        log_info "Run 'vibe env init' to initialize"
        return 0
    fi

    echo "Status: Initialized"
    echo ""

    # Show vibe.yaml info
    if [[ -f "$vibe_home/vibe.yaml" ]]; then
        echo "Configuration: $vibe_home/vibe.yaml"

        if type parse_vibe_yaml >/dev/null 2>&1; then
            parse_vibe_yaml "$vibe_home/vibe.yaml" 2>/dev/null

            local name=$(vibe_yaml_get name "unnamed")
            local version=$(vibe_yaml_get version "unknown")
            echo "  Name: $name"
            echo "  Version: $version"
        fi
    fi
    echo ""

    # Show current keys
    local current_group
    current_group=$(get_current_keys_group 2>/dev/null || echo "unknown")
    echo "Current Keys: $current_group"

    # Count key groups
    local key_count=0
    for f in "$vibe_home/keys"/*.env(N); do
        ((key_count++))
    done
    echo "  Groups available: $key_count"
    echo ""

    # Show tools
    echo "Tools:"
    local tool_count=0
    local enabled_count=0
    if [[ -d "$vibe_home/tools" ]]; then
        for tool_dir in "$vibe_home/tools"/*(N/); do
            local name=$(basename "$tool_dir")
            ((tool_count++))
            if [[ -f "$tool_dir/enabled" ]]; then
                echo "  $name: enabled ✓"
                ((enabled_count++))
            else
                echo "  $name: disabled"
            fi
        done
    fi
    if [[ $tool_count -eq 0 ]]; then
        echo "  No tools installed"
    fi
    echo ""

    # Show MCP
    echo "MCP Servers:"
    if type vibe_yaml_get_list >/dev/null 2>&1; then
        local mcp_list=$(vibe_yaml_get_list mcp 2>/dev/null)
        if [[ -n "$mcp_list" ]]; then
            for mcp in $mcp_list; do
                echo "  $mcp"
            done
        else
            echo "  No MCP servers configured"
        fi
    fi
    echo ""

    # Show skills
    echo "Skills:"
    local skill_count=0
    if [[ -d "$vibe_home/skills" ]]; then
        for skill_file in "$vibe_home/skills"/*.skill.yaml(N); do
            echo "  $(basename "$skill_file" .skill.yaml)"
            ((skill_count++))
        done
    fi
    if [[ $skill_count -eq 0 ]]; then
        echo "  No skills installed"
    fi
}

# Reset the environment
# Usage: vibe_env_reset [--force]
vibe_env_reset() {
    local force="${1:-}"
    local vibe_home="${VIBE_HOME:-$HOME/.vibe}"

    if [[ "$force" != "--force" ]]; then
        log_warn "This will delete all Vibe configuration at: $vibe_home"
        echo ""
        log_info "Are you sure? (yes/no)"
        read -r answer
        if [[ "$answer" != "yes" ]]; then
            log_info "Reset cancelled"
            return 0
        fi
    fi

    # Backup before reset
    if [[ -d "$vibe_home" ]]; then
        local backup="$vibe_home.reset.$(date +%Y%m%d%H%M%S)"
        mv "$vibe_home" "$backup"
        log_info "Backup saved to: $backup"
    fi

    # Reinitialize
    vibe_env_init
    log_success "Environment reset complete"
}
