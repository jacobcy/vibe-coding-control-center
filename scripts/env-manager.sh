#!/usr/bin/env zsh

if [ -z "${ZSH_VERSION:-}" ]; then
    if command -v zsh >/dev/null 2>&1; then exec zsh -l "$0" "$@"; fi
    echo "zsh not found." >&2; exit 1
fi

set -e

SCRIPT_DIR="$(cd "$(dirname "${(%):-%x}")" && pwd)"
source "$SCRIPT_DIR/../lib/utils.sh"
source "$SCRIPT_DIR/../lib/config.sh"
source "$SCRIPT_DIR/../lib/config_init.sh"

KEYS_FILE="$VIBE_HOME/keys.env"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TEMPLATE_FILE="$PROJECT_ROOT/config/keys.template.env"

# ================= HELPERS =================

mask_key() {
    local val="$1"
    if [[ ${#val} -gt 8 ]]; then
        echo "${val:0:4}...${val: -4}"
    elif [[ -n "$val" ]]; then
        echo "****"
    fi
}

should_mask_key() {
    local key="$1"
    # Mask if key name contains sensitive keywords
    [[ "$key" =~ "TOKEN" || "$key" =~ "KEY" || "$key" =~ "AUTH" || "$key" =~ "PASS" || "$key" =~ "SECRET" ]]
}

read_key_from_file() {
    local key="$1" file="$2"
    [[ -f "$file" ]] || { echo ""; return 0; }
    grep -E "^${key}=" "$file" 2>/dev/null | head -1 | cut -d'=' -f2- || echo ""
}

is_template_value() {
    local val="$1"
    [[ "$val" == *"xxxx"* || "$val" == *"xxxxxxxx"* || -z "$val" ]]
}

# ================= STATUS =================

do_status() {
    echo "=== Vibe Environment Status ==="
    echo "Config Home: $VIBE_HOME"
    echo ""

    local default_tool=$(read_key_from_file "VIBE_DEFAULT_TOOL" "$KEYS_FILE")
    local active_tool="${default_tool:-claude}"  # Default to claude if not set
    
    echo "Active Tool: ${GREEN}$active_tool${NC}"
    echo ""

    echo "${BOLD}[Active Key Status]${NC}"
    
    # Define keys to check based on active tool
    local keys_to_check=()
    case "$active_tool" in
        claude)
            keys_to_check=(ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL ANTHROPIC_MODEL)
            ;;
        opencode)
            keys_to_check=(VIBE_OPENCODE_MODEL)
            ;;
        openai)
            keys_to_check=(OPENAI_API_KEY OPENAI_BASE_URL OPENAI_MODEL)
            ;;
        deepseek)
            keys_to_check=(DEEPSEEK_API_KEY DEEPSEEK_BASE_URL DEEPSEEK_MODEL)
            ;;
        moonshot)
            keys_to_check=(MOONSHOT_API_KEY MOONSHOT_BASE_URL MOONSHOT_MODEL)
            ;;
        ollama)
            keys_to_check=(OLLAMA_BASE_URL OLLAMA_MODEL)
            ;;
        *)
            # Fallback or unknown tool
            echo "  (Unknown tool '$active_tool', showing default keys)"
            keys_to_check=(ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL ANTHROPIC_MODEL)
            ;;
    esac

    for key in "${keys_to_check[@]}"; do
        local val=$(read_key_from_file "$key" "$KEYS_FILE")
        if [[ -n "$val" ]] && ! is_template_value "$val"; then
            if should_mask_key "$key"; then
                echo "  $key = $(mask_key "$val")"
            else
                echo "  $key = $val"
            fi
        else
            echo "  $key = ${RED}[NOT SET]${NC}"
        fi
    done

    echo ""
    echo "${BOLD}[Shell] $(get_shell_rc)${NC}"
    local shell_rc=$(get_shell_rc)
    if grep -qF "Vibe Coding" "$shell_rc" 2>/dev/null; then
        echo "  ✅ Vibe configuration present"
    else
        echo "  ❌ Vibe configuration not injected"
    fi

    echo ""
    echo "===" 
    echo "${BOLD}Note:${NC} For AI tool configurations, run: ${CYAN}vibe config${NC}"
}

# ================= DETECT =================

do_detect() {
    log_step "Environment Detection"
    local issues=0

    if [[ ! -d "$VIBE_HOME" ]]; then
        log_warn "~/.vibe/ directory missing. Run: ./scripts/install.sh"
        issues=$((issues + 1))
    fi

    if [[ ! -f "$KEYS_FILE" ]]; then
        log_warn "keys.env not found at $KEYS_FILE"
        issues=$((issues + 1))
    else
        local token=$(read_key_from_file "ANTHROPIC_AUTH_TOKEN" "$KEYS_FILE")
        if is_template_value "$token"; then
            log_warn "ANTHROPIC_AUTH_TOKEN is not configured (still template value)"
            issues=$((issues + 1))
        else
            log_success "ANTHROPIC_AUTH_TOKEN is configured"
        fi
    fi

    if [[ -z "${ANTHROPIC_AUTH_TOKEN:-}" ]]; then
        log_warn "ANTHROPIC_AUTH_TOKEN not in current shell session"
        log_info "  → Run 'vibe env inject' to load keys into current session"
        issues=$((issues + 1))
    else
        log_success "ANTHROPIC_AUTH_TOKEN loaded in current session"
    fi

    if command -v claude &>/dev/null; then
        log_success "Claude CLI found"
    else
        log_warn "Claude CLI not installed"
        issues=$((issues + 1))
    fi

    if command -v opencode &>/dev/null; then
        log_success "OpenCode CLI found"
    else
        log_warn "OpenCode CLI not installed"
        issues=$((issues + 1))
    fi

    if ((issues == 0)); then
        log_success "All checks passed"
    else
        log_warn "$issues issue(s) found"
    fi
}

# ================= SETUP =================

do_setup() {
    log_step "Interactive Environment Setup"

    mkdir -p "$VIBE_HOME"

    if [[ ! -f "$KEYS_FILE" ]]; then
        # Use shared sync logic
        if sync_keys_env "$PROJECT_ROOT"; then
             log_success "Synced project configuration"
        else
             log_error "Setup requires a valid config/keys.env in your project."
             exit 1
        fi
    fi

    local token=$(read_key_from_file "ANTHROPIC_AUTH_TOKEN" "$KEYS_FILE")
    if is_template_value "$token"; then
        log_warn "API keys need to be configured"
        if confirm_action "Open $KEYS_FILE in editor?"; then
            open_editor "$KEYS_FILE"
        fi
    else
        log_success "keys.env appears configured"
        if confirm_action "Edit keys.env?"; then
            open_editor "$KEYS_FILE"
        fi
    fi

    echo ""
    if confirm_action "Inject environment into shell config ($(get_shell_rc))?"; then
        do_inject_rc
    fi

    echo ""
    if confirm_action "Configure MCP servers for Claude (~/.claude.json)?"; then
        do_setup_mcp
    fi

    log_success "Setup complete"
}

# ================= INJECT =================

do_inject_session() {
    [[ -f "$KEYS_FILE" ]] || { log_error "keys.env not found. Run 'vibe env setup' first."; return 1; }
    set -a
    source "$KEYS_FILE"
    set +a
    log_success "Keys exported to current session"
}

do_inject_rc() {
    local shell_rc=$(get_shell_rc)
    local RC_CONTENT="# Vibe Coding Environment
source \"$KEYS_FILE\"
source \"$VIBE_HOME/aliases.sh\"
"
    append_to_rc "$shell_rc" "$RC_CONTENT" "Vibe Coding Environment"
    log_success "Added to $shell_rc"
    log_info "Run: source $shell_rc"
}

# ================= MCP =================

do_setup_mcp() {
    load_keys
    local gh_token=$(config_get_key "GITHUB_PERSONAL_ACCESS_TOKEN")
    local brave_key=$(config_get_key "BRAVE_API_KEY")
    local google_key=$(config_get_key "GOOGLE_GENERATIVE_AI_API_KEY")

    local MCP_CONFIG='{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "'"${gh_token:-}"'"
      }
    },
    "brave-search": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-brave-search"],
      "env": {
        "BRAVE_API_KEY": "'"${brave_key:-}"'"
      }
    },
    "google-generative-ai": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-google-generative-ai"],
      "env": {
        "GOOGLE_GENERATIVE_AI_API_KEY": "'"${google_key:-}"'"
      }
    }
  }
}'

    local MCP_FILE="$HOME/.claude.json"
    if [[ -f "$MCP_FILE" ]]; then
        log_info "Existing MCP config found"
        if confirm_action "Merge with existing config? (No = replace)"; then
            merge_json_configs "$MCP_FILE" "$MCP_CONFIG" "$MCP_FILE" && \
                log_success "MCP merged" || log_warn "Merge failed"
        else
            local backup="${MCP_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
            cp "$MCP_FILE" "$backup"
            log_info "Backed up to $backup"
            echo "$MCP_CONFIG" > "$MCP_FILE"
            chmod 600 "$MCP_FILE"
            log_success "MCP config replaced"
        fi
    else
        echo "$MCP_CONFIG" > "$MCP_FILE"
        chmod 600 "$MCP_FILE"
        log_success "MCP config created"
    fi
}

# ================= SWITCH =================

do_switch() {
    [[ -f "$KEYS_FILE" ]] || { log_error "keys.env not found"; return 1; }
    local endpoint="$1"
    case "$endpoint" in
        china|cn)
            sed -i '' "s|^ANTHROPIC_BASE_URL=.*|ANTHROPIC_BASE_URL=${CUSTOM_CN_ENDPOINT:-https://api.myprovider.com}  # 替换成你的中转站|" "$KEYS_FILE"
            echo "🇨🇳 Switched to China proxy"
            ;;
        official|off)
            sed -i '' "s|^ANTHROPIC_BASE_URL=.*|ANTHROPIC_BASE_URL=https://api.anthropic.com|" "$KEYS_FILE"
            echo "🌐 Switched to official Anthropic"
            ;;
        *)
            echo "Usage: vibe env switch <china|official>"
            return 1
            ;;
    esac
    log_info "Updated $KEYS_FILE. Reload shell to take effect."
}

# ================= KEYS =================

do_keys_show() {
    [[ -f "$KEYS_FILE" ]] || { log_error "keys.env not found"; return 1; }

    echo "=== API Keys (from $KEYS_FILE) ==="
    while IFS= read -r line || [[ -n "$line" ]]; do
        [[ "$line" =~ ^[[:space:]]*# ]] && continue
        [[ -z "${line//[[:space:]]/}" ]] && continue
        if [[ "$line" =~ ^([^=]+)=(.*)$ ]]; then
            local key="${match[1]}"
            local val="${match[2]}"
            # Remove quotes
            val="${val%\"}"
            val="${val#\"}"
            
            if is_template_value "$val"; then
                echo "  ${RED}$key = [NOT SET]${NC}"
            else
                if should_mask_key "$key"; then
                    echo "  ${GREEN}$key = $(mask_key "$val")${NC}"
                else
                    echo "  ${GREEN}$key = $val${NC}"
                fi
            fi
        fi
    done < "$KEYS_FILE"
}

do_keys_edit() {
    [[ -f "$KEYS_FILE" ]] || { log_error "keys.env not found. Run 'vibe env setup' first."; return 1; }
    open_editor "$KEYS_FILE"
    log_info "Reload shell to apply changes: source $(get_shell_rc)"
}

do_keys_verify() {
    [[ -f "$KEYS_FILE" ]] || { log_error "keys.env not found"; return 1; }
    load_keys

    echo "=== Key Verification ==="

    local token=$(config_get_key "ANTHROPIC_AUTH_TOKEN")
    local base_url=$(config_get_key "ANTHROPIC_BASE_URL")
    if [[ -n "$token" ]] && ! is_template_value "$token"; then
        echo -n "  Claude API: "
        local http_code=$(curl -s -o /dev/null -w "%{http_code}" \
            -H "x-api-key: $token" \
            -H "anthropic-version: 2023-06-01" \
            "${base_url:-https://api.anthropic.com}/v1/models" 2>/dev/null || echo "000")
        if [[ "$http_code" == "200" ]]; then
            echo "${GREEN}✅ Valid${NC}"
        elif [[ "$http_code" == "401" ]]; then
            echo "${RED}❌ Invalid token${NC}"
        else
            echo "${YELLOW}⚠️  HTTP $http_code (endpoint may be unavailable)${NC}"
        fi
    else
        echo "  Claude API: ${RED}❌ Token not configured${NC}"
    fi

    local gh_token=$(config_get_key "GITHUB_PERSONAL_ACCESS_TOKEN")
    if [[ -n "$gh_token" ]] && ! is_template_value "$gh_token"; then
        echo -n "  GitHub API: "
        local http_code=$(curl -s -o /dev/null -w "%{http_code}" \
            -H "Authorization: token $gh_token" \
            "https://api.github.com/user" 2>/dev/null || echo "000")
        if [[ "$http_code" == "200" ]]; then
            echo "${GREEN}✅ Valid${NC}"
        else
            echo "${RED}❌ HTTP $http_code${NC}"
        fi
    else
        echo "  GitHub API: ${YELLOW}⚠️  Not configured${NC}"
    fi

    local brave_key=$(config_get_key "BRAVE_API_KEY")
    if [[ -n "$brave_key" ]] && ! is_template_value "$brave_key"; then
        echo "  Brave API: ${GREEN}✅ Configured${NC} ($(mask_key "$brave_key"))"
    else
        echo "  Brave API: ${YELLOW}⚠️  Not configured${NC}"
    fi
}

# ================= MAIN =================

case "${1:-}" in
    status|"")       do_status ;;
    detect|check)    do_detect ;;
    setup|configure) do_setup ;;
    inject)          do_inject_session ;;
    switch)          shift; do_switch "$@" ;;
    keys)
        case "${2:-show}" in
            show)    do_keys_show ;;
            edit)    do_keys_edit ;;
            verify)  do_keys_verify ;;
            *)       echo "Usage: vibe env keys <show|edit|verify>" ;;
        esac
        ;;
    mcp)             do_setup_mcp ;;
    help|-h|--help)
        echo "Vibe Environment Manager"
        echo ""
        echo "Usage: vibe env <command>"
        echo ""
        echo "Commands:"
        echo "  status          Show all tool configurations (default)"
        echo "  detect          Detect and validate environment"
        echo "  setup           Interactive environment setup"
        echo "  inject          Export keys to current shell session"
        echo "  switch <cn|off> Switch Claude endpoint"
        echo "  keys show       Show configured keys (masked)"
        echo "  keys edit       Edit keys.env in editor"
        echo "  keys verify     Test API key validity"
        echo "  mcp             Configure MCP servers"
        ;;
    *)
        echo "Unknown command: $1. Run 'vibe env help' for usage."
        exit 1
        ;;
esac
