#!/bin/bash
# Test status display functionality

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/utils.sh"

echo -e "${CYAN}========================================${NC}"
echo -e "${BOLD}Testing Status Display${NC}"
echo -e "${CYAN}========================================${NC}"

echo -e "\n${BOLD}SYSTEM STATUS:${NC}"

# 1. Claude
if command -v claude &> /dev/null; then
    CLAUDE_VERSION=$(get_command_version "claude" "--version")
    if [[ -n "$CLAUDE_VERSION" ]]; then
        log_info "Claude Code    : Installed (v$CLAUDE_VERSION)"
    else
        log_info "Claude Code    : Installed (version unknown)"
    fi
else
    log_error "Claude Code    : Missing"
fi

# 2. OpenCode
if command -v opencode &> /dev/null; then
    OPENCODE_VERSION=$(get_command_version "opencode" "--version")
    if [[ -n "$OPENCODE_VERSION" ]]; then
        log_info "OpenCode       : Installed (v$OPENCODE_VERSION)"
    else
        log_info "OpenCode       : Installed (version unknown)"
    fi
else
    log_error "OpenCode       : Missing"
fi

# 3. oh-my-opencode
if [ -d "$HOME/.oh-my-opencode" ]; then
    log_info "oh-my-opencode : Installed"
else
    log_warn "oh-my-opencode : Not installed"
fi

# 4. Environment
KEYS_FILE="$SCRIPT_DIR/../config/keys.env"
if [ -f "$KEYS_FILE" ]; then
    log_info "Keys Config    : Found (keys.env)"
else
    log_warn "Keys Config    : Missing (config/keys.env)"
fi

# 5. MCP Configuration
if [ -f "$HOME/.claude.json" ]; then
    SERVER_COUNT=$(grep -o "\"command\"" "$HOME/.claude.json" 2>/dev/null | wc -l | tr -d ' ')
    log_info "MCP Config     : Found ($SERVER_COUNT servers)"
else
    log_warn "MCP Config     : Missing (.claude.json)"
fi

echo -e "\n${CYAN}========================================${NC}"
echo -e "${GREEN}Status Display Test Complete!${NC}"
echo -e "${CYAN}========================================${NC}"

