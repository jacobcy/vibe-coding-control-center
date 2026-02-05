#!/bin/bash
# Modern Installation Script for Vibe Coding Control Center
# This script provides an easier way to install and configure the tool

set -e

# ================= SETUP =================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/utils.sh"
source "$SCRIPT_DIR/lib/config.sh"
source "$SCRIPT_DIR/lib/i18n.sh"

log_step "Starting Modern Installation Process"

# Check prerequisites
log_step "Checking Prerequisites"
REQUIRED_TOOLS=("git" "bash" "curl" "jq")

for tool in "${REQUIRED_TOOLS[@]}"; do
    if ! command -v "$tool" &> /dev/null; then
        log_error "Required tool not found: $tool"
        if [[ "$tool" == "jq" ]]; then
            log_info "Install jq with: brew install jq (macOS) or apt-get install jq (Linux)"
        fi
        exit 1
    fi
done

log_success "All prerequisites satisfied"

# Function to install Claude Code
install_claude_code() {
    log_step "Installing Claude Code"

    if command -v claude &> /dev/null; then
        local current_version
        current_version=$(get_command_version "claude" "--version")
        log_info "Claude Code already installed (v$current_version)"

        if confirm_action "Update Claude Code to latest version?"; then
            if [[ "$OSTYPE" == "darwin"* ]]; then
                if command -v brew &> /dev/null; then
                    log_info "Updating Claude Code via Homebrew..."
                    brew upgrade claude-code
                else
                    log_error "Homebrew not found. Please install Homebrew first."
                    return 1
                fi
            else
                if command -v npm &> /dev/null; then
                    log_info "Updating Claude Code via npm..."
                    npm update -g @anthropic-ai/claude-code
                else
                    log_error "npm not found. Please install Node.js first."
                    return 1
                fi
            fi

            local new_version
            new_version=$(get_command_version "claude" "--version")
            if [[ "$new_version" != "$current_version" ]]; then
                log_success "Updated Claude Code from v$current_version to v$new_version"
            else
                log_info "Claude Code is already up to date"
            fi
        fi
    else
        log_info "Installing Claude Code..."
        if [[ "$OSTYPE" == "darwin"* ]]; then
            if command -v brew &> /dev/null; then
                brew install claude-code
            else
                log_error "Homebrew not found. Please install Homebrew first."
                return 1
            fi
        else
            if command -v npm &> /dev/null; then
                npm install -g @anthropic-ai/claude-code
            else
                log_error "npm not found. Please install Node.js first."
                return 1
            fi
        fi

        local installed_version
        installed_version=$(get_command_version "claude" "--version")
        log_success "Claude Code installed successfully (v$installed_version)"
    fi
}

# Function to install OpenCode
install_opencode() {
    log_step "Installing OpenCode"

    if command -v opencode &> /dev/null; then
        local current_version
        current_version=$(get_command_version "opencode" "--version")
        log_info "OpenCode already installed (v$current_version)"

        if confirm_action "Update OpenCode to latest version?"; then
            log_warn "OpenCode update process not yet implemented in this script"
            log_info "Please follow the manual update instructions in README.md"
        fi
    else
        log_info "OpenCode installation requires manual setup as described in README.md"
        log_info "Please follow the instructions in install/install-opencode.sh"
    fi
}

# Function to setup MCP configuration
setup_mcp_config() {
    log_step "Setting up MCP Configuration"

    local mcp_config_file="$HOME/.claude.json"

    if [[ -f "$mcp_config_file" ]]; then
        log_info "Existing MCP configuration found"
        if confirm_action "Backup and update existing MCP configuration?"; then
            local backup_file="${mcp_config_file}.backup.$(date +%Y%m%d_%H%M%S)"
            if secure_copy "$mcp_config_file" "$backup_file" "false"; then
                log_success "Backed up existing config to: $backup_file"
            fi
        fi
    fi

    # Create or update MCP config based on keys.env
    local keys_file="$SCRIPT_DIR/config/keys.env"
    if [[ -f "$keys_file" ]]; then
        log_info "Using existing keys configuration"
        source "$keys_file"
    else
        log_warn "API keys configuration not found, creating template"
        local template_file="$SCRIPT_DIR/config/keys.template.env"
        if [[ -f "$template_file" ]]; then
            secure_copy "$template_file" "$keys_file" "false"
            log_info "Created keys configuration from template. Please edit $keys_file to add your API keys."
        fi
    fi

    # Generate MCP configuration if API keys are available
    if [[ -n "${GITHUB_PERSONAL_ACCESS_TOKEN:-}" ]] || [[ -n "${BRAVE_API_KEY:-}" ]] || [[ -n "${GOOGLE_GENERATIVE_AI_API_KEY:-}" ]]; then
        log_info "Generating MCP configuration with available API keys"

        local mcp_config='{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "'"${GITHUB_PERSONAL_ACCESS_TOKEN:-""}"'"
      }
    },
    "brave-search": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-brave-search"],
      "env": {
        "BRAVE_API_KEY": "'"${BRAVE_API_KEY:-""}"'"
      }
    },
    "google-generative-ai": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-google-generative-ai"],
      "env": {
        "GOOGLE_GENERATIVE_AI_API_KEY": "'"${GOOGLE_GENERATIVE_AI_API_KEY:-""}"'"
      }
    }
  }
}'

        if secure_write_file "$mcp_config_file" "$mcp_config" "600"; then
            log_success "MCP configuration created/updated successfully"
        else
            log_error "Failed to create MCP configuration"
            return 1
        fi
    else
        log_warn "No API keys found. MCP configuration will be created without server credentials."
        log_info "Please edit $keys_file to add your API keys and run this setup again."
    fi
}

# Function to setup shell aliases
setup_aliases() {
    log_step "Setting up Shell Aliases"

    local shell_rc
    shell_rc=$(get_shell_rc)

    if ! validate_path "$shell_rc" "Shell RC file path validation failed"; then
        log_error "Invalid shell RC file path: $shell_rc"
        return 1
    fi

    # Prepare alias configuration
    local alias_content='# Vibe Coding Configuration
export ANTHROPIC_AUTH_TOKEN='"${ANTHROPIC_AUTH_TOKEN:-""}"'
export ANTHROPIC_BASE_URL='"${ANTHROPIC_BASE_URL:-https://api.anthropic.com}"'
export ANTHROPIC_MODEL='"${ANTHROPIC_MODEL:-claude-3-5-sonnet-20241022}"'
source "'"$SCRIPT_DIR"'"/config/aliases.sh
'

    if validate_input "$alias_content" "false"; then
        append_to_rc "$shell_rc" "$alias_content" "Vibe Coding Configuration"
    else
        log_error "Generated alias configuration failed validation"
        return 1
    fi
}

# Main installation flow
log_success "Starting Vibe Coding Control Center installation"

if confirm_action "Install Claude Code?"; then
    install_claude_code
fi

if confirm_action "Install OpenCode?"; then
    install_opencode
fi

if confirm_action "Setup MCP configuration?"; then
    setup_mcp_config
fi

if confirm_action "Setup shell aliases?"; then
    setup_aliases
fi

log_success "Installation process completed!"
log_info "Please run: source $SHELL_RC (or your respective shell config file)"
log_info "Then you can use the 'vibe' command to start the control center"