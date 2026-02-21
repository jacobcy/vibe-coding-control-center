#!/usr/bin/env zsh
# lib/mcp_manager.sh
# MCP server management library for Vibe environment

# Resolve script directory for sourcing dependencies
_mcp_manager_dir="$(cd "$(dirname "${(%):-%x}")" && pwd)"

# Source dependencies
if [[ -f "${_mcp_manager_dir}/utils.sh" ]]; then
    source "${_mcp_manager_dir}/utils.sh"
fi
if [[ -f "${_mcp_manager_dir}/config.sh" ]]; then
    source "${_mcp_manager_dir}/config.sh"
fi

# MCP directory location
VIBE_MCP_DIR="${VIBE_HOME:-$HOME/.vibe}/mcp"

# Known MCP servers
typeset -gA VIBE_KNOWN_MCP
VIBE_KNOWN_MCP=(
    github "GitHub integration - repositories, issues, PRs"
    brave-search "Brave Search - web search capabilities"
    filesystem "Filesystem - file and directory operations"
    memory "Memory - persistent memory storage"
    notion "Notion - workspace integration"
)

# List all MCP servers
# Usage: vibe_mcp_list
vibe_mcp_list() {
    echo "Available MCP servers:"

    # Get configured servers from vibe.yaml
    local configured=""
    if type vibe_yaml_get_list >/dev/null 2>&1; then
        configured=$(vibe_yaml_get_list mcp 2>/dev/null)
    fi

    local found=0

    # List known MCP servers
    for mcp_name in ${(k)VIBE_KNOWN_MCP}; do
        local mcp_desc="${VIBE_KNOWN_MCP[$mcp_name]}"
        local marker=""

        # Check if in configured list
        if [[ " $configured " == *" $mcp_name "* ]]; then
            marker=" ✓"
        fi

        echo "  $mcp_name$marker"
        echo "    └─ $mcp_desc"
        found=1
    done

    # List any custom MCP servers from directory
    if [[ -d "$VIBE_MCP_DIR/servers" ]]; then
        for mcp_file in "$VIBE_MCP_DIR/servers"/*.yaml(N); do
            local name=$(basename "$mcp_file" .yaml)
            # Skip if already listed as known
            [[ -n "${VIBE_KNOWN_MCP[$name]:-}" ]] && continue

            local marker=""
            if [[ " $configured " == *" $name "* ]]; then
                marker=" ✓"
            fi

            echo "  $name$marker (custom)"
            found=1
        done
    fi

    if [[ $found -eq 0 ]]; then
        echo "  No MCP servers configured"
    fi

    if [[ -n "$configured" ]]; then
        echo ""
        echo "Configured servers: $configured"
    fi
}

# Add an MCP server
# Usage: vibe_mcp_add <server_name> [--for <tool>]
vibe_mcp_add() {
    local mcp="$1"
    local tool="${2:-}"

    if [[ -z "$mcp" ]]; then
        log_error "MCP server name required"
        echo "Usage: vibe mcp add <server-name> [--for <tool>]"
        echo ""
        echo "Known servers: ${(k)VIBE_KNOWN_MCP}"
        return 1
    fi

    local yaml_file="$VIBE_HOME/vibe.yaml"

    if [[ ! -f "$yaml_file" ]]; then
        log_error "vibe.yaml not found. Run 'vibe init' first."
        return 1
    fi

    # Check if already configured
    local configured
    configured=$(vibe_yaml_get_list mcp 2>/dev/null)

    if [[ " $configured " == *" $mcp "* ]]; then
        log_warn "MCP server already configured: $mcp"
        return 0
    fi

    # Add to mcp list in vibe.yaml
    # Simple approach: append to the mcp section
    if grep -q "^mcp:" "$yaml_file"; then
        # Find mcp section and add the new item
        # This is a simple implementation; a proper YAML parser would be better
        sed -i '' "/^mcp:/a\\
  - $mcp
" "$yaml_file" 2>/dev/null || \
        sed -i "/^mcp:/a\\  - $mcp
" "$yaml_file" 2>/dev/null
    else
        # Add mcp section
        echo "" >> "$yaml_file"
        echo "mcp:" >> "$yaml_file"
        echo "  - $mcp" >> "$yaml_file"
    fi

    log_success "Added MCP server: $mcp"

    # If --for specified, also add to tool-specific config
    if [[ -n "$tool" ]]; then
        local tool_dir="$VIBE_HOME/tools/$tool"
        if [[ -d "$tool_dir" ]]; then
            echo "  - $mcp" >> "$tool_dir/mcp.yaml"
            log_info "Also added to $tool MCP config"
        fi
    fi
}

# Remove an MCP server
# Usage: vibe_mcp_remove <server_name>
vibe_mcp_remove() {
    local mcp="$1"

    if [[ -z "$mcp" ]]; then
        log_error "MCP server name required"
        echo "Usage: vibe mcp remove <server-name>"
        return 1
    fi

    local yaml_file="$VIBE_HOME/vibe.yaml"

    if [[ ! -f "$yaml_file" ]]; then
        log_error "vibe.yaml not found"
        return 1
    fi

    # Remove from mcp list (simple approach)
    # This removes the line matching "  - $mcp"
    sed -i '' "/^  - $mcp$/d" "$yaml_file" 2>/dev/null || \
    sed -i "/^  - $mcp$/d" "$yaml_file" 2>/dev/null

    log_success "Removed MCP server: $mcp"
}

# Enable MCP for a specific tool
# Usage: vibe_mcp_enable <server_name> --for <tool>
vibe_mcp_enable() {
    local mcp="$1"
    shift

    if [[ "$1" == "--for" ]]; then
        shift
    fi
    local tool="$1"

    if [[ -z "$mcp" || -z "$tool" ]]; then
        log_error "Both MCP server and tool name required"
        echo "Usage: vibe mcp enable <server> --for <tool>"
        return 1
    fi

    local tool_dir="$VIBE_HOME/tools/$tool"

    if [[ ! -d "$tool_dir" ]]; then
        log_error "Tool not installed: $tool"
        return 1
    fi

    # Add to tool's MCP config
    if ! grep -q "^  - $mcp$" "$tool_dir/mcp.yaml" 2>/dev/null; then
        # Ensure file has proper structure
        if [[ ! -s "$tool_dir/mcp.yaml" ]] || ! grep -q "^mcp:" "$tool_dir/mcp.yaml" 2>/dev/null; then
            echo "mcp:" > "$tool_dir/mcp.yaml"
        fi
        echo "  - $mcp" >> "$tool_dir/mcp.yaml"
    fi

    log_success "Enabled $mcp for $tool"
}

# Disable MCP for a specific tool
# Usage: vibe_mcp_disable <server_name> --for <tool>
vibe_mcp_disable() {
    local mcp="$1"
    shift

    if [[ "$1" == "--for" ]]; then
        shift
    fi
    local tool="$1"

    if [[ -z "$mcp" || -z "$tool" ]]; then
        log_error "Both MCP server and tool name required"
        echo "Usage: vibe mcp disable <server> --for <tool>"
        return 1
    fi

    local tool_dir="$VIBE_HOME/tools/$tool"
    local mcp_file="$tool_dir/mcp.yaml"

    if [[ ! -f "$mcp_file" ]]; then
        log_warn "No MCP config for tool: $tool"
        return 0
    fi

    sed -i '' "/^  - $mcp$/d" "$mcp_file" 2>/dev/null || \
    sed -i "/^  - $mcp$/d" "$mcp_file" 2>/dev/null

    log_success "Disabled $mcp for $tool"
}
