#!/usr/bin/env zsh
# Claude Code Installation Script
# Refactored for Security & Modularity

if [ -z "${ZSH_VERSION:-}" ]; then
    if command -v zsh >/dev/null 2>&1; then
        exec zsh -l "$0" "$@"
    fi
    echo "zsh not found. Please run ./scripts/install.sh to install zsh." >&2
    exit 1
fi

set -e

# ================= SETUP =================
SCRIPT_DIR="$(cd "$(dirname "${(%):-%x}")" && pwd)"
source "$SCRIPT_DIR/../lib/utils.sh"

log_step "1/6 Check & Cone Dependencies"
REPO_URL="https://github.com/affaan-m/everything-claude-code"
PROJECT_DIR="$SCRIPT_DIR/../everything-claude-code"

# Validate paths
if ! validate_path "$PROJECT_DIR" "Project directory validation failed"; then
    log_critical "Invalid project directory: $PROJECT_DIR"
    exit 1
fi

if [ -d "$PROJECT_DIR" ]; then
    log_info "everything-claude-code exists"
else
    # Create directory with proper permissions
    if ! mkdir -p "$PROJECT_DIR" 2>/dev/null; then
        log_critical "Failed to create project directory: $PROJECT_DIR"
        exit 1
    fi

    # Validate that git command exists
    if ! check_command_exists "git"; then
        log_critical "git command not found, please install git first"
        exit 1
    fi

    git clone "$REPO_URL" "$PROJECT_DIR" 2>/dev/null || {
        log_warn "Clone failed, using local fallback"
        PROJECT_DIR="$SCRIPT_DIR"
    }
fi

# ================= CLAUDE CLI =================
log_step "2/6 Check & Update Claude CLI"
if command -v claude &> /dev/null; then
    # Get current version
    CURRENT_VERSION=$(get_command_version "claude" "--version")

    if [[ -n "$CURRENT_VERSION" ]]; then
        log_info "Claude CLI already installed (version: $CURRENT_VERSION)"
    else
        log_info "Claude CLI already installed (version: unknown)"
    fi

    # Ask if user wants to update
    if confirm_action "Do you want to update Claude CLI to the latest version?"; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            if ! check_command_exists "brew"; then
                log_warn "Homebrew not found. Skipping update."
            else
                update_via_brew "claude-code"

                # Show new version
                NEW_VERSION=$(get_command_version "claude" "--version")
                if [[ -n "$NEW_VERSION" && "$NEW_VERSION" != "$CURRENT_VERSION" ]]; then
                    log_success "Updated from $CURRENT_VERSION to $NEW_VERSION"
                fi
            fi
        else
            if ! check_command_exists "npm"; then
                log_warn "npm not found. Skipping update."
            else
                update_via_npm "@anthropic-ai/claude-code"

                # Show new version
                NEW_VERSION=$(get_command_version "claude" "--version")
                if [[ -n "$NEW_VERSION" && "$NEW_VERSION" != "$CURRENT_VERSION" ]]; then
                    log_success "Updated from $CURRENT_VERSION to $NEW_VERSION"
                fi
            fi
        fi
    else
        log_info "Skipping Claude CLI update"
    fi
else
    log_warn "Installing Claude CLI..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        if ! check_command_exists "brew"; then
            log_critical "Homebrew not found. Please install Homebrew first: https://brew.sh/"
            exit 1
        fi
        brew install claude-code
    else
        if ! check_command_exists "npm"; then
            log_critical "npm not found. Please install Node.js first."
            exit 1
        fi
        npm install -g @anthropic-ai/claude-code
    fi

    # Show installed version
    INSTALLED_VERSION=$(get_command_version "claude" "--version")
    if [[ -n "$INSTALLED_VERSION" ]]; then
        log_success "Claude CLI installed (version: $INSTALLED_VERSION)"
    fi
fi

# ================= SECRETS & ENV =================
log_step "3/6 Configure Environment & Secrets"
KEYS_FILE="$SCRIPT_DIR/../config/keys.env"
TEMPLATE_FILE="$SCRIPT_DIR/../config/keys.template.env"

# Validate paths
if ! validate_path "$KEYS_FILE" "Keys file path validation failed"; then
    log_critical "Invalid keys file path: $KEYS_FILE"
    exit 1
fi

if ! validate_path "$TEMPLATE_FILE" "Template file path validation failed"; then
    log_critical "Invalid template file path: $TEMPLATE_FILE"
    exit 1
fi

if [ ! -f "$KEYS_FILE" ]; then
    log_warn "Secrets file not found!"

    # Validate template exists before copying
    if [ ! -f "$TEMPLATE_FILE" ]; then
        log_critical "Template file not found: $TEMPLATE_FILE"
        exit 1
    fi

    # Use secure copy function
    if ! secure_copy "$TEMPLATE_FILE" "$KEYS_FILE" "false"; then
        log_critical "Failed to create keys file from template"
        exit 1
    fi

    log_info "Created config/keys.env from template."
    echo -e "${RED}ACTION REQUIRED: Edit $KEYS_FILE and add your API keys before proceeding.${NC}"
    echo "Press Enter once you have edited the file..."
    read
fi

# Validate keys file before sourcing
if [ ! -f "$KEYS_FILE" ] || [ ! -r "$KEYS_FILE" ]; then
    log_critical "Keys file is not accessible: $KEYS_FILE"
    exit 1
fi

# Load keys to current session for immediate use
set -a
source "$KEYS_FILE"
set +a

# Write to Shell RC
SHELL_RC=$(get_shell_rc)

# Validate shell rc path
if ! validate_path "$SHELL_RC" "Shell RC file path validation failed"; then
    log_critical "Invalid shell RC file path: $SHELL_RC"
    exit 1
fi

# Prepare configuration content with proper validation
RC_CONTENT="# Vibe Coding Configuration
export ANTHROPIC_AUTH_TOKEN=\"${ANTHROPIC_AUTH_TOKEN}\"
export ANTHROPIC_BASE_URL=\"${ANTHROPIC_BASE_URL}\"
export ANTHROPIC_MODEL=\"${ANTHROPIC_MODEL}\"
source \"${SCRIPT_DIR}/../config/aliases.sh\"
"

# Validate content for potential security issues
if ! validate_input "$RC_CONTENT" "false"; then
    log_critical "Generated configuration content failed validation"
    exit 1
fi

# Append to shell RC with validation
append_to_rc "$SHELL_RC" "$RC_CONTENT" "Vibe Coding Configuration"

# ================= DIRECTORIES =================
log_step "4/6 Create Directories"
CONFIG_DIRS=("$HOME/.claude/agents" "$HOME/.claude/rules" "$HOME/.claude/commands" "$HOME/.claude/skills")

for dir in "${CONFIG_DIRS[@]}"; do
    # Validate directory path
    if ! validate_path "$dir" "Config directory path validation failed"; then
        log_warn "Skipping invalid config directory: $dir"
        continue
    fi

    if ! mkdir -p "$dir" 2>/dev/null; then
        log_warn "Failed to create directory: $dir"
    fi
done

# ================= ASSETS =====================
log_step "5/6 Copy Assets"

# Ask user if they want to copy enhanced configurations
if confirm_action "Do you want to copy enhanced configurations (agents, rules, commands, skills) to ~/.claude?"; then
    ASSET_DIRS=("rules" "agents" "commands")

    for asset_dir in "${ASSET_DIRS[@]}"; do
        SRC_DIR="$PROJECT_DIR/$asset_dir"

        # Validate source directory
        if [[ -d "$SRC_DIR" ]]; then
            if ! validate_path "$SRC_DIR" "Asset source directory validation failed"; then
                log_warn "Skipping invalid asset directory: $SRC_DIR"
                continue
            fi

            DEST_DIR="$HOME/.claude/$asset_dir"

            # Validate destination directory
            if ! validate_path "$DEST_DIR" "Asset destination directory validation failed"; then
                log_warn "Skipping invalid asset destination: $DEST_DIR"
                continue
            fi

            # Create destination if it doesn't exist
            mkdir -p "$DEST_DIR" 2>/dev/null || {
                log_warn "Could not create destination directory: $DEST_DIR"
                continue
            }

            # Copy assets with error handling
            if ! cp "$SRC_DIR/"*.md "$DEST_DIR/" 2>/dev/null; then
                log_warn "No .md files found in $SRC_DIR or copy failed"
            else
                log_success "Copied $asset_dir configurations to $DEST_DIR"
            fi
        fi
    done

    # Copy skills separately
    SKILLS_SRC_DIR="$PROJECT_DIR/skills"
    if [[ -d "$SKILLS_SRC_DIR" ]]; then
        if ! validate_path "$SKILLS_SRC_DIR" "Skills source directory validation failed"; then
            log_warn "Invalid skills source directory: $SKILLS_SRC_DIR"
        else
            SKILLS_DEST_DIR="$HOME/.claude/skills"
            if ! validate_path "$SKILLS_DEST_DIR" "Skills destination directory validation failed"; then
                log_warn "Invalid skills destination directory: $SKILLS_DEST_DIR"
            else
                mkdir -p "$SKILLS_DEST_DIR" 2>/dev/null || {
                    log_warn "Could not create skills destination directory: $SKILLS_DEST_DIR"
                }

                if ! cp -r "$SKILLS_SRC_DIR/"* "$SKILLS_DEST_DIR/" 2>/dev/null; then
                    log_warn "Failed to copy skills from $SKILLS_SRC_DIR"
                else
                    log_success "Copied skills to $SKILLS_DEST_DIR"
                fi
            fi
        fi
    fi

    log_success "Enhanced configurations copied successfully"
else
    log_info "Skipping enhanced configurations copy"
fi

# ================= MCP CONFIG =================
log_step "6/6 Configure MCP"
# Use keys from environment with validation

# Validate that required environment variables exist
REQUIRED_VARS=("GITHUB_PERSONAL_ACCESS_TOKEN" "BRAVE_API_KEY" "GOOGLE_GENERATIVE_AI_API_KEY")
MISSING_VARS=()

for var in "${REQUIRED_VARS[@]}"; do
    if [[ -z "${!var:-}" ]]; then
        MISSING_VARS+=("$var")
    fi
done

if [[ ${#MISSING_VARS[@]} -gt 0 ]]; then
    log_warn "Missing required API keys: ${MISSING_VARS[*]}"
    log_warn "Please check your $KEYS_FILE and add the missing keys."
fi

# Validate home directory path before creating config file
if ! validate_path "$HOME/.claude.json" "MCP config file path validation failed"; then
    log_critical "Invalid MCP config file path: $HOME/.claude.json"
    exit 1
fi

MCP_CONFIG='{
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

# Validate configuration content before writing
if ! validate_input "$MCP_CONFIG" "true"; then
    log_critical "Generated MCP configuration failed validation"
    exit 1
fi

# Handle MCP config - merge if exists, otherwise create new
MCP_CONFIG_FILE="$HOME/.claude.json"

if [[ -f "$MCP_CONFIG_FILE" ]]; then
    log_info "Existing MCP configuration found"

    if confirm_action "Do you want to merge with existing MCP configuration? (No = replace)"; then
        # Merge configurations
        if merge_json_configs "$MCP_CONFIG_FILE" "$MCP_CONFIG" "$MCP_CONFIG_FILE"; then
            log_success "MCP configuration merged successfully"
        else
            log_warn "Merge failed, configuration replaced with backup created"
        fi
    else
        # Backup and replace
        BACKUP_FILE="${MCP_CONFIG_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
        if secure_copy "$MCP_CONFIG_FILE" "$BACKUP_FILE" "false"; then
            log_info "Backed up existing config to: $BACKUP_FILE"
        fi

        if ! secure_write_file "$MCP_CONFIG_FILE" "$MCP_CONFIG" "600"; then
            log_critical "Failed to write MCP configuration"
            exit 1
        fi
        log_success "MCP configuration replaced"
    fi
else
    # Create new config
    if ! secure_write_file "$MCP_CONFIG_FILE" "$MCP_CONFIG" "600"; then
        log_critical "Failed to write MCP configuration"
        exit 1
    fi
    log_success "MCP configuration created"
fi

echo -e "\n${GREEN}Installation Complete!${NC}"
echo "Please run: source $SHELL_RC"
