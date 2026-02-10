#!/bin/bash
# Test script for new version detection and update features

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/utils.sh"

echo -e "${CYAN}========================================${NC}"
echo -e "${BOLD}Testing New Features${NC}"
echo -e "${CYAN}========================================${NC}"

# Test 0: Plugin-style command entrypoints
echo -e "\n${YELLOW}Test 0: Vibe Plugin Entrypoints${NC}"
echo "-----------------------------------"

BIN_DIR="$SCRIPT_DIR/../bin"
if [[ -x "$BIN_DIR/vibe" ]]; then
    log_success "✓ bin/vibe exists and is executable"
else
    log_error "✗ bin/vibe missing or not executable"
fi

for sub in chat init keys sync diagnostics equip; do
    if [[ -x "$BIN_DIR/vibe-$sub" ]]; then
        log_success "✓ bin/vibe-$sub exists and is executable"
    else
        log_error "✗ bin/vibe-$sub missing or not executable"
    fi
done

# Check new lib modules
if [[ -f "$SCRIPT_DIR/../lib/agents.sh" ]]; then
    log_success "✓ lib/agents.sh exists"
else
    log_error "✗ lib/agents.sh missing"
fi

if [[ -f "$SCRIPT_DIR/../lib/init_project.sh" ]]; then
    log_success "✓ lib/init_project.sh exists"
else
    log_error "✗ lib/init_project.sh missing"
fi

# Test 1: Version detection functions
echo -e "\n${YELLOW}Test 1: Version Detection Functions${NC}"
echo "-----------------------------------"

# Test get_command_version
if command -v git &> /dev/null; then
    GIT_VERSION=$(get_command_version "git" "--version")
    if [[ -n "$GIT_VERSION" ]]; then
        log_success "✓ get_command_version works: git v$GIT_VERSION"
    else
        log_error "✗ get_command_version failed for git"
    fi
else
    log_warn "git not installed, skipping test"
fi

# Test with non-existent command
FAKE_VERSION=$(get_command_version "nonexistentcommand123" "--version" || true)
if [[ -z "$FAKE_VERSION" ]]; then
    log_success "✓ get_command_version correctly returns empty for non-existent command"
else
    log_error "✗ get_command_version should return empty for non-existent command"
fi

# Test 2: Version comparison
echo -e "\n${YELLOW}Test 2: Version Comparison${NC}"
echo "-----------------------------------"

if version_equal "1.2.3" "1.2.3"; then
    log_success "✓ Version comparison: 1.2.3 == 1.2.3"
else
    log_error "✗ Version comparison failed: 1.2.3 should equal 1.2.3"
fi

if version_greater_than "2.0.0" "1.9.9"; then
    log_success "✓ Version comparison: 2.0.0 > 1.9.9"
else
    log_error "✗ Version comparison failed: 2.0.0 should be greater than 1.9.9"
fi

if version_less_than "1.5.0" "1.10.0"; then
    log_success "✓ Version comparison: 1.5.0 < 1.10.0"
else
    log_error "✗ Version comparison failed: 1.5.0 should be less than 1.10.0"
fi

if ! version_greater_than "1.5.0" "2.0.0"; then
    log_success "✓ Version comparison: 1.5.0 not > 2.0.0"
else
    log_error "✗ Version comparison failed: 1.5.0 should not be greater than 2.0.0"
fi

# Test 3: Check installed tools
echo -e "\n${YELLOW}Test 3: Installed Tools Detection${NC}"
echo "-----------------------------------"

if command -v claude &> /dev/null; then
    CLAUDE_VERSION=$(get_command_version "claude" "--version")
    if [[ -n "$CLAUDE_VERSION" ]]; then
        log_info "Claude Code: v$CLAUDE_VERSION"
    else
        log_info "Claude Code: installed (version unknown)"
    fi
else
    log_warn "Claude Code: not installed"
fi

if command -v opencode &> /dev/null; then
    OPENCODE_VERSION=$(get_command_version "opencode" "--version")
    if [[ -n "$OPENCODE_VERSION" ]]; then
        log_info "OpenCode: v$OPENCODE_VERSION"
    else
        log_info "OpenCode: installed (version unknown)"
    fi
else
    log_warn "OpenCode: not installed"
fi

if [ -f "$HOME/.oh-my-opencode/install.sh" ]; then
    log_info "oh-my-opencode: installed"
else
    log_warn "oh-my-opencode: not installed"
fi

# Test 4: JSON merge capability check
echo -e "\n${YELLOW}Test 4: JSON Merge Capability${NC}"
echo "-----------------------------------"

if command -v jq &> /dev/null; then
    JQ_VERSION=$(get_command_version "jq" "--version")
    log_success "✓ jq is available (v$JQ_VERSION) - JSON merge will work properly"
else
    log_warn "⚠ jq not available - will use backup and replace method for MCP config"
fi

# Test 5: MCP Configuration check
echo -e "\n${YELLOW}Test 5: MCP Configuration Status${NC}"
echo "-----------------------------------"

if [ -f "$HOME/.claude.json" ]; then
    SERVER_COUNT=$(grep -o "\"command\"" "$HOME/.claude.json" 2>/dev/null | wc -l | tr -d ' ')
    log_info "MCP config exists with $SERVER_COUNT servers"
    
    # Show server names
    if command -v jq &> /dev/null; then
        echo -e "${CYAN}Configured MCP servers:${NC}"
        jq -r '.mcpServers | keys[]' "$HOME/.claude.json" 2>/dev/null | while read server; do
            echo "  - $server"
        done
    fi
else
    log_warn "MCP config not found at $HOME/.claude.json"
fi

echo -e "\n${CYAN}========================================${NC}"
echo -e "${GREEN}Testing Complete!${NC}"
echo -e "${CYAN}========================================${NC}"
